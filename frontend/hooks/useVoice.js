'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { resolveSpeechLocale, splitTextForGeminiTts, cleanTextForSpeech, safeReadJson } from '../lib/pageUtils';
import { apiFetch } from '../lib/api';

export function useVoice({ language, onTranscriptRef }) {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [speechCapabilities, setSpeechCapabilities] = useState({ input: false, output: false });
  const [selectedVoiceUri, setSelectedVoiceUri] = useState('');
  const [ttsProvider, setTtsProvider] = useState('browser');

  const speechRecognitionRef = useRef(null);
  const activeAudioRef = useRef(null);
  const audioContextRef = useRef(null);
  const activeAudioSourceRef = useRef(null);
  const ttsPlaybackTokenRef = useRef(0);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setSpeechCapabilities({
      input: 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window,
      output: 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined'
    });
  }, []);

  const stopVoiceInput = useCallback(() => {
    const recognition = speechRecognitionRef.current;
    if (!recognition) return;
    recognition.stop();
  }, []);

  const ensureUnlockedAudioContext = useCallback(async () => {
    if (typeof window === 'undefined') return null;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;
    if (!audioContextRef.current) audioContextRef.current = new AudioContextClass();
    if (audioContextRef.current.state === 'suspended') {
      try { await audioContextRef.current.resume(); } catch (_) {}
    }
    return audioContextRef.current;
  }, []);

  const base64ToArrayBuffer = (base64) => {
    const binaryString = window.atob(String(base64 || ''));
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i += 1) bytes[i] = binaryString.charCodeAt(i);
    return bytes.buffer;
  };

  const playGeminiAudioWithWebAudio = async (audioBase64) => {
    const context = await ensureUnlockedAudioContext();
    if (!context) return false;
    const encodedBuffer = base64ToArrayBuffer(audioBase64);
    const decodedBuffer = await context.decodeAudioData(encodedBuffer.slice(0));
    if (activeAudioSourceRef.current) {
      try { activeAudioSourceRef.current.stop(); } catch (_) {}
      activeAudioSourceRef.current = null;
    }
    const source = context.createBufferSource();
    source.buffer = decodedBuffer;
    source.connect(context.destination);
    activeAudioSourceRef.current = source;
    return new Promise((resolve, reject) => {
      source.onended = () => {
        if (activeAudioSourceRef.current === source) activeAudioSourceRef.current = null;
        resolve(true);
      };
      try { source.start(0); } catch (err) {
        if (activeAudioSourceRef.current === source) activeAudioSourceRef.current = null;
        reject(err);
      }
    });
  };

  const playGeminiAudioWithHtmlAudio = async (audioBase64, mimeType = 'audio/mpeg') => {
    const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
    activeAudioRef.current = audio;
    return new Promise((resolve, reject) => {
      audio.onended = () => {
        if (activeAudioRef.current === audio) activeAudioRef.current = null;
        resolve(true);
      };
      audio.onerror = () => {
        if (activeAudioRef.current === audio) activeAudioRef.current = null;
        reject(new Error(language === 'de' ? 'Gemini-Audio konnte nicht abgespielt werden.' : 'Gemini audio playback failed.'));
      };
      audio.play().catch(reject);
    });
  };

  const stopAudioPlayback = useCallback(() => {
    ttsPlaybackTokenRef.current += 1;
    const activeAudio = activeAudioRef.current;
    if (activeAudio) {
      try { activeAudio.pause(); } catch (_) {}
      activeAudioRef.current = null;
    }
    if (activeAudioSourceRef.current) {
      try { activeAudioSourceRef.current.stop(); } catch (_) {}
      activeAudioSourceRef.current = null;
    }
    setIsSpeaking(false);
  }, []);

  const speakAssistantText = useCallback((text) => {
    const prepared = cleanTextForSpeech(text).slice(0, 1100);
    if (!prepared) return;

    const speakWithBrowser = () => {
      if (!speechCapabilities.output) return;
      try {
        stopAudioPlayback();
        window.speechSynthesis.cancel();
        const utterance = new window.SpeechSynthesisUtterance(prepared);
        const locale = resolveSpeechLocale(language);
        utterance.lang = locale;
        utterance.rate = 1;
        utterance.pitch = 1;
        const browserVoices = window.speechSynthesis.getVoices();
        const selectedVoice = selectedVoiceUri
          ? browserVoices.find((voice) => voice.voiceURI === selectedVoiceUri)
          : null;
        const matchingVoice = selectedVoice
          || browserVoices.find((voice) => voice.lang?.toLowerCase().startsWith(language.toLowerCase()))
          || browserVoices.find((voice) => voice.lang?.toLowerCase().startsWith(locale.slice(0, 2).toLowerCase()));
        if (matchingVoice) utterance.voice = matchingVoice;
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        utterance.onerror = () => { setIsSpeaking(false); setVoiceError(language === 'de' ? 'Sprachausgabe fehlgeschlagen.' : 'Text-to-speech failed.'); };
        window.speechSynthesis.speak(utterance);
      } catch (err) {
        setIsSpeaking(false);
        setVoiceError(language === 'de' ? 'Sprachausgabe nicht verfuegbar.' : 'Text-to-speech is unavailable.');
      }
    };

    const speakWithGeminiFallback = async (playbackToken) => {
      const chunks = splitTextForGeminiTts(prepared, 260);
      if (!chunks.length) return;
      for (const chunk of chunks) {
        if (playbackToken !== ttsPlaybackTokenRef.current) return;
        const response = await apiFetch('/api/tts/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: chunk, language_code: resolveSpeechLocale(language) })
        });
        const data = await safeReadJson(response);
        if (!response.ok || data?.success === false || !data?.audio_base64) {
          throw new Error(data?.error || `Gemini TTS request failed (${response.status})`);
        }
        if (playbackToken !== ttsPlaybackTokenRef.current) return;
        try { await playGeminiAudioWithWebAudio(data.audio_base64); }
        catch (_) { await playGeminiAudioWithHtmlAudio(data.audio_base64, data?.mime_type || 'audio/mpeg'); }
      }
    };

    const speakWithGemini = async () => {
      let currentPlaybackToken = 0;
      try {
        stopAudioPlayback();
        ttsPlaybackTokenRef.current += 1;
        currentPlaybackToken = ttsPlaybackTokenRef.current;
        if (speechCapabilities.output) window.speechSynthesis.cancel();
        setIsSpeaking(true);
        setVoiceError('');
        const response = await apiFetch('/api/tts/live', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: prepared, language_code: resolveSpeechLocale(language) })
        });
        if (!response.ok || !response.body) {
          await speakWithGeminiFallback(currentPlaybackToken);
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let gotAudio = false;
        let streamError = '';
        let playbackChain = Promise.resolve();
        const enqueueAudioChunk = (audioBase64, mimeType) => {
          playbackChain = playbackChain.then(async () => {
            if (currentPlaybackToken !== ttsPlaybackTokenRef.current) return;
            try {
              const playedWithWebAudio = await playGeminiAudioWithWebAudio(audioBase64);
              if (!playedWithWebAudio) await playGeminiAudioWithHtmlAudio(audioBase64, mimeType || 'audio/wav');
            } catch (_) { await playGeminiAudioWithHtmlAudio(audioBase64, mimeType || 'audio/wav'); }
          });
        };
        let streamDone = false;
        while (!streamDone) {
          const { value, done } = await reader.read();
          if (done) { streamDone = true; }
          else {
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed) continue;
              let event = null;
              try { event = JSON.parse(trimmed); } catch { continue; }
              if (event?.type === 'audio' && event?.audio_base64) { gotAudio = true; enqueueAudioChunk(event.audio_base64, event.mime_type); }
              if (event?.type === 'error') streamError = String(event.error || 'Live stream failed');
              if (event?.type === 'done') streamDone = true;
            }
          }
          if (currentPlaybackToken !== ttsPlaybackTokenRef.current) {
            try { await reader.cancel(); } catch (_) {}
            return;
          }
        }
        if (streamError) throw new Error(streamError);
        if (buffer.trim()) {
          try {
            const lastEvent = JSON.parse(buffer.trim());
            if (lastEvent?.type === 'audio' && lastEvent?.audio_base64) { gotAudio = true; enqueueAudioChunk(lastEvent.audio_base64, lastEvent.mime_type); }
            if (lastEvent?.type === 'error') throw new Error(String(lastEvent.error || 'Live stream failed'));
          } catch (err) { if (err instanceof Error) throw err; }
        }
        await playbackChain;
        if (!gotAudio) await speakWithGeminiFallback(currentPlaybackToken);
      } catch (err) {
        if (currentPlaybackToken && currentPlaybackToken !== ttsPlaybackTokenRef.current) return;
        try { await speakWithGeminiFallback(currentPlaybackToken); return; }
        catch (fallbackErr) {
          const fallbackMessage = fallbackErr?.message || err?.message || 'Unknown error';
          setVoiceError(language === 'de'
            ? `Gemini-TTS Fehler: ${fallbackMessage}. Fallback auf Browser-Stimme.`
            : `Gemini TTS error: ${fallbackMessage}. Falling back to browser voice.`);
          speakWithBrowser();
        }
      } finally {
        if (currentPlaybackToken && currentPlaybackToken === ttsPlaybackTokenRef.current) {
          setIsSpeaking(false);
        }
      }
    };

    if (ttsProvider === 'gemini') { speakWithGemini(); return; }
    speakWithBrowser();
  // Playback helpers operate on refs and the current request; changing their function identity must not recreate speech mid-flight.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language, stopAudioPlayback, speechCapabilities.output, selectedVoiceUri, ttsProvider]);

  const startVoiceInput = useCallback(() => {
    if (!speechCapabilities.input) {
      setVoiceError(language === 'de' ? 'Spracheingabe wird von diesem Browser nicht unterstuetzt.' : 'Speech recognition is not supported in this browser.');
      return;
    }
    if (isListening) { stopVoiceInput(); return; }
    const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!RecognitionClass) {
      setVoiceError(language === 'de' ? 'Spracheingabe ist nicht verfuegbar.' : 'Speech recognition is unavailable.');
      return;
    }
    let finalTranscript = '';
    const recognition = new RecognitionClass();
    speechRecognitionRef.current = recognition;
    recognition.lang = resolveSpeechLocale(language);
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;
    recognition.onstart = () => { setVoiceError(''); setIsListening(true); };
    recognition.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0]?.transcript || '';
        if (event.results[i].isFinal) finalTranscript += ` ${text}`;
      }
    };
    recognition.onerror = (event) => {
      const code = String(event.error || '');
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        setVoiceError(language === 'de' ? 'Mikrofonzugriff wurde verweigert.' : 'Microphone permission was denied.');
      } else if (code !== 'aborted') {
        setVoiceError(language === 'de' ? `Spracheingabe-Fehler: ${code}` : `Speech input error: ${code}`);
      }
    };
    recognition.onend = () => {
      setIsListening(false);
      speechRecognitionRef.current = null;
      const transcript = finalTranscript.trim();
      if (transcript && onTranscriptRef?.current) onTranscriptRef.current(transcript, { fromVoice: true });
    };
    recognition.start();
  }, [language, isListening, onTranscriptRef, speechCapabilities.input, stopVoiceInput]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const unlockAudio = () => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      if (!audioContextRef.current) audioContextRef.current = new AudioContextClass();
      if (audioContextRef.current.state === 'suspended') audioContextRef.current.resume().catch(() => {});
    };
    window.addEventListener('pointerdown', unlockAudio, { passive: true });
    window.addEventListener('keydown', unlockAudio);
    return () => {
      window.removeEventListener('pointerdown', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (speechRecognitionRef.current) { speechRecognitionRef.current.stop(); speechRecognitionRef.current = null; }
      if (activeAudioRef.current) {
        try { activeAudioRef.current.pause(); } catch (_) {}
        activeAudioRef.current = null;
      }
      if (activeAudioSourceRef.current) {
        try { activeAudioSourceRef.current.stop(); } catch (_) {}
        activeAudioSourceRef.current = null;
      }
      if (audioContextRef.current) { audioContextRef.current.close().catch(() => {}); audioContextRef.current = null; }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
    };
  }, []);

  return {
    isListening, isSpeaking, voiceError,
    speechRecognitionSupported: speechCapabilities.input,
    speechSynthesisSupported: speechCapabilities.output,
    selectedVoiceUri, setSelectedVoiceUri,
    ttsProvider, setTtsProvider,
    startVoiceInput, stopVoiceInput, speakAssistantText, stopAudioPlayback
  };
}
