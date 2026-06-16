/**
 * Dropzone — image upload + multi-image describe (V1, V2, V4).
 *
 * Native drag-and-drop or click-to-upload. After each upload we render a
 * thumbnail strip with the returned id; the "Describe" button calls the
 * vision endpoint with all current ids and the user's question.
 */
import { useCallback, useRef, useState } from "react"
import { Loader2, Trash2, Upload, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  describeImages,
  uploadImage,
  type UploadedImage,
} from "@/lib/uploads-api"
import { cn } from "@/lib/utils"

const ACCEPT = "image/png,image/jpeg,image/webp"

type Item = UploadedImage & { previewUrl: string; name: string }

export function Dropzone() {
  const [items, setItems] = useState<Item[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [question, setQuestion] = useState(
    "What is in these images? Summarise for a wealth manager.",
  )
  const [answer, setAnswer] = useState<string | null>(null)
  const [thinking, setThinking] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    setError(null)
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        try {
          const up = await uploadImage(file)
          setItems((prev) => [
            ...prev,
            {
              ...up,
              previewUrl: URL.createObjectURL(file),
              name: file.name,
            },
          ])
        } catch (e) {
          const err = e as { status?: number; message?: string; workaround?: string }
          setError(
            err.workaround
              ? `${err.message} — ${err.workaround}`
              : err.message ?? "upload failed",
          )
        }
      }
    } finally {
      setUploading(false)
    }
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setDragOver(false)
      if (e.dataTransfer.files?.length) {
        void handleFiles(e.dataTransfer.files)
      }
    },
    [handleFiles],
  )

  const remove = (id: string) =>
    setItems((prev) => prev.filter((p) => p.id !== id))

  const clear = () => {
    items.forEach((i) => URL.revokeObjectURL(i.previewUrl))
    setItems([])
    setAnswer(null)
  }

  const ask = useCallback(async () => {
    if (!items.length) return
    setThinking(true)
    setAnswer(null)
    try {
      const res = await describeImages(
        items.map((i) => i.id),
        question,
      )
      setAnswer(res.description)
    } catch (e) {
      setError(e instanceof Error ? e.message : "describe failed")
    } finally {
      setThinking(false)
    }
  }, [items, question])

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Upload images</CardTitle>
        </CardHeader>
        <CardContent>
          <div
            data-testid="dropzone"
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed py-10 text-sm transition",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/30 hover:border-muted-foreground/60",
            )}
          >
            <Upload className="h-6 w-6 text-muted-foreground" />
            <p className="font-medium">
              Drop images here or click to upload
            </p>
            <p className="text-xs text-muted-foreground">
              PNG, JPG, WebP — up to 25 MB
            </p>
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              data-testid="file-input"
              onChange={(e) => {
                if (e.target.files) void handleFiles(e.target.files)
                e.target.value = ""
              }}
            />
          </div>

          {error && (
            <p
              role="alert"
              className="mt-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {error}
            </p>
          )}

          {uploading && (
            <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> uploading…
            </p>
          )}

          {items.length > 0 && (
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-3">
                {items.map((i) => (
                  <div
                    key={i.id}
                    className="group relative overflow-hidden rounded-md border"
                  >
                    <img
                      src={i.previewUrl}
                      alt={i.name}
                      className="h-24 w-32 object-cover"
                    />
                    <span className="absolute bottom-0 left-0 truncate bg-background/80 px-1.5 py-0.5 text-[10px] font-mono">
                      {i.id.slice(0, 8)}
                    </span>
                    <button
                      type="button"
                      aria-label="remove"
                      onClick={() => remove(i.id)}
                      className="absolute right-1 top-1 rounded-full bg-background/80 p-1 opacity-0 transition group-hover:opacity-100"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={clear}
                className="text-muted-foreground"
              >
                <Trash2 className="h-3.5 w-3.5" /> clear all
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ask about these images</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="What should the model look at?"
            rows={2}
          />
          <Button
            onClick={ask}
            disabled={!items.length || thinking}
            data-testid="describe-btn"
          >
            {thinking ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> describing…
              </>
            ) : (
              <>Describe {items.length} image{items.length === 1 ? "" : "s"}</>
            )}
          </Button>

          {answer && (
            <div
              data-testid="vision-answer"
              className="whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm"
            >
              {answer}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
