/** Client-side photo compression for prescription uploads (ROADMAP M3: ≤ 1 MB per image).
 *  Downscales to at most `maxSide` pixels and re-encodes as JPEG, lowering quality until it fits. */
export async function compressImage(file: File, maxBytes = 1_000_000, maxSide = 2000): Promise<File> {
  if (file.size <= maxBytes && /^image\/(jpeg|png|webp)$/.test(file.type)) return file;
  const bitmap = await createImageBitmap(file);
  let scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  let quality = 0.85;
  for (let attempt = 0; attempt < 8; attempt++) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) break;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
    if (blob && blob.size <= maxBytes) {
      bitmap.close();
      return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
    }
    if (quality > 0.55) quality -= 0.1;
    else scale *= 0.8;
  }
  bitmap.close();
  throw new Error("IMAGE_TOO_LARGE");
}
