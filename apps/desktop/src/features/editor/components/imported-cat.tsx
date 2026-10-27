import { useEffect, useRef } from "react";

export function ImportedCat() {
  const hostRef = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let disposed = false;
    let cleanup: (() => void) | undefined;
    // Keep the animation renderer outside the initial application bundle.
    void Promise.all([
      import("lottie-web/build/player/lottie_light"),
      import("../assets/cat-playing.json"),
    ])
      .then(([{ default: lottie }, { default: data }]) => {
        if (disposed) return;
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
        const animation = lottie.loadAnimation({
          container: host,
          renderer: "svg",
          loop: true,
          autoplay: false,
          animationData: structuredClone(data),
          rendererSettings: { progressiveLoad: true },
        });
        animation.setSubframe(false);
        const updatePlayback = () => {
          if (reducedMotion.matches) animation.goToAndStop(0, true);
          else if (document.hidden) animation.pause();
          else animation.play();
        };
        animation.addEventListener("DOMLoaded", updatePlayback);
        reducedMotion.addEventListener("change", updatePlayback);
        document.addEventListener("visibilitychange", updatePlayback);
        updatePlayback();
        cleanup = () => {
          reducedMotion.removeEventListener("change", updatePlayback);
          document.removeEventListener("visibilitychange", updatePlayback);
          animation.destroy();
        };
      })
      .catch(() => {
        // This decorative animation must never interrupt the editor.
      });
    return () => {
      disposed = true;
      cleanup?.();
    };
  }, []);
  return (
    <span
      ref={hostRef}
      aria-hidden="true"
      className="pointer-events-none absolute -bottom-1 inline-block h-7 w-16"
    />
  );
}
