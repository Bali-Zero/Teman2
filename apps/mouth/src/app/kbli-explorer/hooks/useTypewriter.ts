import { useState, useEffect, useCallback, useRef } from "react";

interface UseTypewriterReturn {
  displayText: string;
  isTyping: boolean;
  skip: () => void;
}

export function useTypewriter(
  text: string,
  speed: number = 15,
): UseTypewriterReturn {
  const [displayText, setDisplayText] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const skipRef = useRef(false);
  const textRef = useRef(text);

  // When new text arrives, start typing
  useEffect(() => {
    if (!text) {
      setDisplayText("");
      setIsTyping(false);
      return;
    }

    // If same text, don't re-type
    if (text === textRef.current && displayText === text) return;
    textRef.current = text;
    skipRef.current = false;
    setIsTyping(true);
    setDisplayText("");

    let idx = 0;
    const tick = () => {
      if (skipRef.current || idx >= text.length) {
        setDisplayText(text);
        setIsTyping(false);
        return;
      }
      // Type 1-3 chars per tick for natural feel
      const chunk = Math.min(
        text.length - idx,
        Math.random() > 0.7 ? 3 : text[idx] === " " ? 2 : 1,
      );
      idx += chunk;
      setDisplayText(text.slice(0, idx));
      timer = setTimeout(tick, speed + Math.random() * 10);
    };

    let timer = setTimeout(tick, speed);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, speed]);

  const skip = useCallback(() => {
    skipRef.current = true;
    setDisplayText(textRef.current);
    setIsTyping(false);
  }, []);

  return { displayText, isTyping, skip };
}
