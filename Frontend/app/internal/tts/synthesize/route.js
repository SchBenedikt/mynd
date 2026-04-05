import { GoogleGenAI } from '@google/genai';
import { promises as fs } from 'node:fs';
import path from 'node:path';

export const runtime = 'nodejs';

const BACKEND_TTS_URL = process.env.MYND_BACKEND_TTS_URL || 'http://127.0.0.1:5001/api/tts/synthesize';
const FALLBACK_MODEL = process.env.GEMINI_TTS_MODEL || 'gemini-2.5-flash-preview-tts';
const FALLBACK_VOICE = process.env.GEMINI_TTS_VOICE || 'Kore';
const BACKEND_AI_CONFIG_FILE = path.resolve(process.cwd(), '../backend/config/ai_config.json');

function trimUtf8Bytes(value, maxBytes) {
  const buffer = Buffer.from(String(value || ''), 'utf-8');
  if (buffer.byteLength <= maxBytes) return String(value || '');
  return buffer.subarray(0, maxBytes).toString('utf-8');
}

function parseMimeType(mimeType) {
  const [fileType, ...params] = String(mimeType || '').split(';').map((s) => s.trim());
  const [, format] = fileType.split('/');

  const options = {
    numChannels: 1,
    sampleRate: 24000,
    bitsPerSample: 16,
  };

  if (format && format.startsWith('L')) {
    const bits = Number.parseInt(format.slice(1), 10);
    if (!Number.isNaN(bits)) {
      options.bitsPerSample = bits;
    }
  }

  for (const param of params) {
    const [key, value] = param.split('=').map((s) => s.trim());
    if (key === 'rate') {
      const sampleRate = Number.parseInt(value, 10);
      if (!Number.isNaN(sampleRate) && sampleRate > 0) {
        options.sampleRate = sampleRate;
      }
    }
  }

  return options;
}

function createWavHeader(dataLength, options) {
  const { numChannels, sampleRate, bitsPerSample } = options;
  const byteRate = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign = numChannels * bitsPerSample / 8;
  const buffer = Buffer.alloc(44);

  buffer.write('RIFF', 0);
  buffer.writeUInt32LE(36 + dataLength, 4);
  buffer.write('WAVE', 8);
  buffer.write('fmt ', 12);
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(numChannels, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(byteRate, 28);
  buffer.writeUInt16LE(blockAlign, 32);
  buffer.writeUInt16LE(bitsPerSample, 34);
  buffer.write('data', 36);
  buffer.writeUInt32LE(dataLength, 40);

  return buffer;
}

function pcmToWavBase64(rawBase64, mimeType) {
  const pcmBuffer = Buffer.from(String(rawBase64 || ''), 'base64');
  const options = parseMimeType(mimeType);
  const wavHeader = createWavHeader(pcmBuffer.length, options);
  return Buffer.concat([wavHeader, pcmBuffer]).toString('base64');
}

async function tryBackendTts(payload) {
  try {
    const response = await fetch(BACKEND_TTS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      cache: 'no-store',
    });

    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { error: text || `Backend TTS failed (${response.status})` };
    }

    if (!response.ok || data?.success === false || !data?.audio_base64) {
      return { ok: false, status: response.status, data };
    }

    return { ok: true, status: response.status, data };
  } catch (error) {
    return { ok: false, status: 0, data: { error: String(error?.message || error) } };
  }
}

function extractAudioPart(response) {
  const candidates = response?.candidates || [];
  for (const candidate of candidates) {
    const parts = candidate?.content?.parts || [];
    for (const part of parts) {
      if (part?.inlineData?.data) {
        return part.inlineData;
      }
    }
  }
  return null;
}

async function loadBackendAiConfig() {
  try {
    const content = await fs.readFile(BACKEND_AI_CONFIG_FILE, 'utf-8');
    const parsed = JSON.parse(content);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export async function POST(request) {
  try {
    const body = await request.json().catch(() => ({}));
    const text = trimUtf8Bytes(body?.text || '', 8000).trim();

    if (!text) {
      return Response.json({ success: false, error: 'text darf nicht leer sein' }, { status: 400 });
    }

    const backendResult = await tryBackendTts({
      text,
      language_code: body?.language_code,
      prompt: body?.prompt,
      model: body?.model,
      voice: body?.voice,
      audio_encoding: body?.audio_encoding,
    });

    if (backendResult.ok) {
      return Response.json(backendResult.data);
    }

    const persistedConfig = await loadBackendAiConfig();

    const apiKey = String(
      process.env.GEMINI_API_KEY
      || process.env.GOOGLE_API_KEY
      || persistedConfig.gemini_tts_api_key
      || ''
    ).trim();
    if (!apiKey) {
      return Response.json(
        {
          success: false,
          error: `Backend TTS nicht verfuegbar (${backendResult.status || 'network'}) und kein Gemini API Key gefunden (weder .env noch Settings).`,
        },
        { status: 500 }
      );
    }

    const prompt = trimUtf8Bytes(body?.prompt || persistedConfig.gemini_tts_style_prompt || '', 4000).trim();
    const languageCode = String(body?.language_code || persistedConfig.gemini_tts_language_code || 'de-DE').trim() || 'de-DE';
    const model = String(body?.model || persistedConfig.gemini_tts_model || FALLBACK_MODEL).trim() || FALLBACK_MODEL;
    const voiceName = String(body?.voice || persistedConfig.gemini_tts_voice || FALLBACK_VOICE).trim() || FALLBACK_VOICE;

    const combinedText = prompt ? `${prompt}\n\n${text}` : text;

    const ai = new GoogleGenAI({ apiKey });
    const response = await ai.models.generateContent({
      model,
      config: {
        temperature: 1,
        responseModalities: ['audio'],
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: {
              voiceName,
            },
          },
        },
      },
      contents: [
        {
          role: 'user',
          parts: [
            {
              text: `Language: ${languageCode}\n\n${combinedText}`,
            },
          ],
        },
      ],
    });

    const inlineData = extractAudioPart(response);
    if (!inlineData?.data) {
      return Response.json({ success: false, error: 'Keine Audiodaten von Gemini erhalten' }, { status: 502 });
    }

    const originalMime = String(inlineData.mimeType || '').trim();
    const needsWavContainer = /^audio\/L\d+/i.test(originalMime);
    const audioBase64 = needsWavContainer
      ? pcmToWavBase64(inlineData.data, originalMime)
      : inlineData.data;
    const mimeType = needsWavContainer ? 'audio/wav' : (originalMime || 'audio/wav');

    return Response.json({
      success: true,
      audio_base64: audioBase64,
      mime_type: mimeType,
      model,
      voice: voiceName,
      language_code: languageCode,
      source: 'frontend-genai-fallback',
    });
  } catch (error) {
    return Response.json(
      {
        success: false,
        error: String(error?.message || error),
      },
      { status: 500 }
    );
  }
}
