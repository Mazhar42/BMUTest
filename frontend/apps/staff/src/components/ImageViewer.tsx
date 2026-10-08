import { useI18n } from "@bmu/i18n";
import { Button, cn, Skeleton } from "@bmu/ui";
import { RotateCw, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useState } from "react";

import { protectedImage } from "../lib/api";

/** Prescription pages next to the tests: page tabs, zoom and rotate (ROADMAP M3). */
export function ImageViewer({ prescriptionId, pages }: { prescriptionId: string; pages: number }) {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [rotate, setRotate] = useState(0);
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let url: string | null = null;
    let cancelled = false;
    setSrc(null);
    setFailed(false);
    protectedImage(`/api/v1/staff/prescriptions/${prescriptionId}/images/${page}`)
      .then((u) => {
        url = u;
        if (!cancelled) setSrc(u);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [prescriptionId, page]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-sand-200 bg-sand-900">
      <div className="flex items-center gap-2 border-b border-white/10 px-3 py-2">
        <div className="flex gap-1">
          {Array.from({ length: pages }, (_, i) => i + 1).map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setPage(n)}
              className={cn(
                "rounded-lg px-2.5 py-1 text-[12.5px] font-semibold",
                n === page ? "bg-white text-ink" : "text-white/60 hover:bg-white/10",
              )}
            >
              {t("staff.verify.page", { n })}
            </button>
          ))}
        </div>
        <div className="ml-auto flex gap-1">
          <Button size="sm" variant="ghost" className="text-white/70 hover:bg-white/10 hover:text-white" aria-label="zoom out" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>
            <ZoomOut className="size-4" />
          </Button>
          <span className="w-12 self-center text-center text-[12px] tabular text-white/60">{Math.round(zoom * 100)}%</span>
          <Button size="sm" variant="ghost" className="text-white/70 hover:bg-white/10 hover:text-white" aria-label="zoom in" onClick={() => setZoom((z) => Math.min(4, z + 0.25))}>
            <ZoomIn className="size-4" />
          </Button>
          <Button size="sm" variant="ghost" className="text-white/70 hover:bg-white/10 hover:text-white" aria-label="rotate" onClick={() => setRotate((r) => (r + 90) % 360)}>
            <RotateCw className="size-4" />
          </Button>
        </div>
      </div>
      <div className="relative min-h-[420px] flex-1 overflow-auto scrollbar-thin">
        {src ? (
          <div className="grid min-h-full place-items-center p-4">
            <img
              src={src}
              alt={t("staff.verify.page", { n: page })}
              style={{ transform: `rotate(${rotate}deg) scale(${zoom})`, transformOrigin: "center" }}
              className="max-h-[70vh] max-w-full rounded-md bg-white shadow-lift transition-transform"
            />
          </div>
        ) : failed ? (
          <p className="p-10 text-center text-[13px] text-white/60">{t("staff.verify.imageFailed")}</p>
        ) : (
          <Skeleton className="m-6 h-[380px] bg-white/10" />
        )}
      </div>
    </div>
  );
}
