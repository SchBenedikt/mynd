import { GoogleGenAI, MediaResolution, Modality } from '@google/genai';
import { promises as fs } from 'node:fs';
import path from 'node:path';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const FALLBACK_LIVE_MODEL = process.env.GEMINI_LIVE_MODEL || 'models/gemini-3.1-flash-live-preview';
const FALLBACK_VOICE = process.env.GEMINI_LIVE_VOICE || 'Zephyr';
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

function normalizeLiveModel(modelName) {
  const base = String(modelName || '').trim();
  if (!base) return FALLBACK_LIVE_MODEL;
  if (base.startsWith('models/')) return base;
  return `models/${base}`;
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

function buildLivePayload({ body, persistedConfig }) {
  const prompt = trimUtf8Bytes(body?.prompt || persistedConfig.gemini_tts_style_prompt || '', 4000).trim();
  const text = trimUtf8Bytes(body?.text || '', 8000).trim();
  const languageCode = String(body?.language_code || persistedConfig.gemini_tts_language_code || 'de-DE').trim() || 'de-DE';
  const voiceName = String(body?.voice || process.env.GEMINI_LIVE_VOICE || persistedConfig.gemini_live_voice || FALLBACK_VOICE).trim() || FALLBACK_VOICE;
  const model = normalizeLiveModel(body?.model || process.env.GEMINI_LIVE_MODEL || persistedConfig.gemini_live_model || FALLBACK_LIVE_MODEL);

  const mergedText = prompt ? `${prompt}\n\n${text}` : text;
  return {
    model,
    languageCode,
    voiceName,
    userText: `Language: ${languageCode}\n\n${mergedText}`,
  };
}

export async function POST(request) {
  const encoder = new TextEncoder();

  try {
    const body = await request.json().catch(() => ({}));
    const text = trimUtf8Bytes(body?.text || '', 8000).trim();

    if (!text) {
      return Response.json({ success: false, error: 'text darf nicht leer sein' }, { status: 400 });
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
          error: 'Kein Gemini API Key gefunden (weder .env noch Settings).',
        },
        { status: 500 }
      );
    }

    const payload = buildLivePayload({ body: { ...body, text }, persistedConfig });

    let session;
    const stream = new ReadableStream({
      async start(controller) {
        const send = (event) => {
          controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`));
        };

        let emittedAudio = false;
        let turnFinished = false;

        const closeSafe = () => {
          try {
            controller.close();
          } catch {
            // ignore close errors when stream already closed
          }
        };

        try {
          const ai = new GoogleGenAI({ apiKey });
          session = await ai.live.connect({
            model: payload.model,
            config: {
                responseModalities: [Modality?.AUDIO || 'AUDIO'],
                mediaResolution: MediaResolution?.MEDIA_RESOLUTION_LOW || 'MEDIA_RESOLUTION_LOW',
              speechConfig: {
                voiceConfig: {
                  prebuiltVoiceConfig: {
                    voiceName: payload.voiceName,
                  },
                },
              },
                contextWindowCompression: {
                  triggerTokens: '52428',
                  slidingWindow: { targetTokens: '26214' },
                },
                tools: [
                  {
                    functionDeclarations: [],
                  },
                ],
            },
            callbacks: {
              onmessage: (message) => {
                const parts = message?.serverContent?.modelTurn?.parts || [];
                for (const part of parts) {
                  if (part?.inlineData?.data) {
                    const originalMime = String(part.inlineData.mimeType || '').trim();
                    const needsWavContainer = /^audio\/(L\d+|pcm)/i.test(originalMime);
                    const audioBase64 = needsWavContainer
                      ? pcmToWavBase64(part.inlineData.data, originalMime)
                      : String(part.inlineData.data || '');
                    const mimeType = needsWavContainer ? 'audio/wav' : (originalMime || 'audio/wav');
                    emittedAudio = true;
                    send({ type: 'audio', audio_base64: audioBase64, mime_type: mimeType });
                  }

                  if (part?.text) {
                    send({ type: 'text', text: String(part.text) });
                  }
                }

                if (message?.serverContent?.turnComplete) {
                  turnFinished = true;
                  send({ type: 'done' });
                  try {
                    session?.close();
                  } catch {
                    // ignore close errors on closed session
                  }
                  closeSafe();
                }
              },
              onerror: (event) => {
                const rawError = String(event?.message || 'Live connection failed');
                const normalized = /invalid argument/i.test(rawError)
                  ? 'Live API rejected the request (invalid argument). This API key likely has no Live bidiGenerateContent access for the selected model.'
                  : rawError;
                send({ type: 'error', error: normalized });
                closeSafe();
              },
              onclose: (event) => {
                if (!turnFinished && !emittedAudio) {
                  const reason = String(event?.reason || '').trim();
                  const normalized = /invalid argument/i.test(reason)
                    ? 'Live API rejected the request (invalid argument). This API key likely has no Live bidiGenerateContent access for the selected model.'
                    : (reason || 'Live session closed without audio.');
                  send({ type: 'error', error: normalized });
                }
                send({ type: 'done' });
                closeSafe();
              },
            },
          });

          session.sendClientContent({
            turns: [payload.userText],
          });
        } catch (error) {
          send({ type: 'error', error: String(error?.message || error) });
          closeSafe();
        }
      },
      cancel() {
        try {
          session?.close();
        } catch {
          // ignore close errors on cancelled streams
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'application/x-ndjson; charset=utf-8',
        'Cache-Control': 'no-cache, no-transform',
      },
    });
  } catch (error) {
    return Response.json({ success: false, error: String(error?.message || error) }, { status: 500 });
  }
}
