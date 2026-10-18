/** Live, self-playing view of the 3D lobby (rendered with three.js) for the dashboard. */
export function mountPreview(
  canvas: HTMLCanvasElement,
  options?: { onFrame?: () => void },
): { dispose(): void }
