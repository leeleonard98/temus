/**
 * Page wrapper for the uploads feature — used by the /uploads route.
 */
import { Dropzone } from "@/features/uploads/Dropzone"

export function UploadsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Vision uploads</h2>
        <p className="text-sm text-muted-foreground">
          Upload portfolio screenshots, charts, or document scans and ask the
          model to describe them.
        </p>
      </div>
      <Dropzone />
    </div>
  )
}
