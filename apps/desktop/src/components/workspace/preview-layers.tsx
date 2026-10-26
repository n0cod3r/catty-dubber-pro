import type { TimelineDocument } from "@/features/timeline/model";

export function PreviewLayers({
  document,
  currentTime,
  width,
  frontVideoIndex,
}: {
  document: TimelineDocument;
  currentTime: number;
  width: number;
  frontVideoIndex: number;
}) {
  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-label="Live layer composition"
    >
      {document.layers.map((layer, index) =>
        layer.hidden || (frontVideoIndex >= 0 && index > frontVideoIndex)
          ? null
          : document.clips
              .filter(
                (clip) =>
                  clip.trackId === layer.id &&
                  (clip.kind === "subtitle" || clip.kind === "graphic") &&
                  currentTime >= clip.start &&
                  currentTime < clip.start + clip.duration,
              )
              .map((clip) => (
                <div
                  key={clip.id}
                  data-preview-clip={clip.id}
                  style={{
                    zIndex: document.layers.length - index,
                    fontSize: Math.max(12, width * (clip.kind === "subtitle" ? 0.035 : 0.06)),
                    color: clip.kind === "subtitle" ? "white" : clip.color,
                  }}
                  className={
                    clip.kind === "subtitle"
                      ? "absolute right-[5%] bottom-[8%] left-[5%] text-center leading-relaxed font-semibold whitespace-pre-wrap [text-shadow:0_2px_4px_black,0_0_2px_black]"
                      : "absolute inset-0 flex items-center justify-center p-[5%] text-center leading-tight font-bold whitespace-pre-wrap [text-shadow:0_2px_8px_black]"
                  }
                >
                  {clip.kind === "subtitle" ? (
                    <span className="rounded bg-black/60 px-2 py-1 box-decoration-clone">
                      {clip.text}
                    </span>
                  ) : (
                    clip.text
                  )}
                </div>
              )),
      )}
    </div>
  );
}
