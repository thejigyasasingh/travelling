import { useState } from 'react'
import type { PropertyImage } from '@/domain/property'
import { Modal } from '@/ui/Modal'
import { cn } from '@/ui/cn'

/**
 * The photo gallery.
 *
 * The first image is eager with `fetchPriority="high"` — it is the largest
 * contentful paint on this page, and lazy-loading it delays the one thing the
 * guest came to see. Every other image is lazy.
 */
export function Gallery({ images, name }: { images: readonly PropertyImage[]; name: string }) {
  const [lightbox, setLightbox] = useState<number | null>(null)

  if (images.length === 0) {
    return (
      <div className="grid aspect-[16/9] place-items-center rounded-2xl bg-ink-100 text-ink-400">
        No photos yet
      </div>
    )
  }

  const [hero, ...rest] = images
  const thumbs = rest.slice(0, 4)

  return (
    <>
      <div className="grid gap-2 overflow-hidden rounded-2xl md:grid-cols-4 md:grid-rows-2">
        <button
          type="button"
          onClick={() => setLightbox(0)}
          className="relative aspect-[4/3] md:col-span-2 md:row-span-2 md:aspect-auto"
        >
          <img
            src={hero?.url}
            alt={hero?.altText ?? `${name}, main photo`}
            fetchPriority="high"
            className="size-full object-cover transition-transform hover:scale-[1.02]"
          />
        </button>

        {thumbs.map((image, index) => (
          <button
            key={image.id}
            type="button"
            onClick={() => setLightbox(index + 1)}
            className="relative hidden aspect-[4/3] md:block"
          >
            <img
              src={image.url}
              alt={image.altText ?? `${name}, photo ${index + 2}`}
              loading="lazy"
              className="size-full object-cover transition-transform hover:scale-[1.02]"
            />
            {index === thumbs.length - 1 && images.length > 5 && (
              <span className="absolute inset-0 grid place-items-center bg-ink-900/50 text-sm font-medium text-white">
                +{images.length - 5} more
              </span>
            )}
          </button>
        ))}
      </div>

      <Modal
        open={lightbox !== null}
        onClose={() => setLightbox(null)}
        title={`${name} — photos`}
        size="lg"
      >
        <div className="space-y-3">
          <img
            src={images[lightbox ?? 0]?.url}
            alt={images[lightbox ?? 0]?.altText ?? name}
            className="w-full rounded-xl object-contain"
          />
          {images[lightbox ?? 0]?.caption && (
            <p className="text-sm text-ink-600">{images[lightbox ?? 0]?.caption}</p>
          )}
          <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
            {images.map((image, index) => (
              <button
                key={image.id}
                type="button"
                onClick={() => setLightbox(index)}
                aria-label={`Photo ${index + 1} of ${images.length}`}
                aria-current={index === lightbox}
                className={cn(
                  'size-16 shrink-0 overflow-hidden rounded-lg border-2',
                  index === lightbox ? 'border-brand-600' : 'border-transparent',
                )}
              >
                <img src={image.url} alt="" loading="lazy" className="size-full object-cover" />
              </button>
            ))}
          </div>
        </div>
      </Modal>
    </>
  )
}
