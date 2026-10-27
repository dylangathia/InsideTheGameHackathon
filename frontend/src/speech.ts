import { useEffect, useState } from "react";

/**
 * The Pundit's voice, read by the browser's own speech synthesis. Only offered when the browser has a voice for
 * the viewer's language: no voice means no button, never a fallback to another language.
 */
export function useVoice(lang: string): SpeechSynthesisVoice | null {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(null);
  useEffect(() => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) return;
    const pick = () => {
      const voices = synth.getVoices().filter((v) => v.lang.toLowerCase().split(/[-_]/)[0] === lang);
      setVoice(voices.find((v) => v.localService) ?? voices[0] ?? null);
    };
    pick();
    // Browsers load their voices lazily and don't always fire "voiceschanged", so also look again for a few seconds.
    let tries = 0;
    const poll = setInterval(() => {
      pick();
      if (++tries >= 10) clearInterval(poll);
    }, 500);
    synth.addEventListener("voiceschanged", pick);
    return () => {
      clearInterval(poll);
      synth.removeEventListener("voiceschanged", pick);
    };
  }, [lang]);
  return voice;
}

/** Speak `text`; calls `onEnd` when finished (or straight away if speech fails). Cancels anything already speaking. */
export function speak(text: string, voice: SpeechSynthesisVoice, onEnd: () => void): void {
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.voice = voice;
  u.lang = voice.lang;
  u.rate = 1.02;
  u.onend = onEnd;
  u.onerror = onEnd;
  synth.speak(u);
}

export function stopSpeaking(): void {
  window.speechSynthesis?.cancel();
}
