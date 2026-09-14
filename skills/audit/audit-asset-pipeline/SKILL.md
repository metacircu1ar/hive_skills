---
name: audit-asset-pipeline
description: Audit upload handling and asset delivery for web applications. Use when reviewing file uploads, media storage, generated assets, public file serving, CDN/object storage integration, or hosting cost/performance risks caused by storing user uploads on the application server.
---

# Audit Asset Pipeline

Find uploads or generated assets stored on the app server and assess whether delivery should use object storage and a CDN.

## Workflow

1. Locate asset ingestion:
   - File upload routes, multipart handlers, image/video/audio processing, generated PDFs/images, avatars, attachments, imports, exports, and admin media tools.
2. Locate storage targets:
   - Local filesystem writes, framework static/public directories, temp directories, database blobs, object storage SDKs, and third-party media services.
3. Locate delivery paths:
   - Static file serving, signed download URLs, proxy endpoints, CDN config, cache headers, image transforms, and public URL generation.
4. Flag risky patterns:
   - User uploads written to the application server or repo directory.
   - Local disk storage in container/serverless environments where files disappear on redeploy.
   - Large files proxied through app workers instead of object storage/CDN.
   - No cache headers or CDN for frequently loaded media.
   - Missing file size, MIME/type validation, virus scanning expectations, or access controls for private assets.
5. Recommend a target architecture:
   - Object storage for durable uploads.
   - CDN for public assets.
   - Signed URLs or authenticated proxy only where privacy requires it.
   - Background processing for expensive transforms.

## Useful Searches

Search for asset terms such as `upload`, `multipart`, `file`, `avatar`, `attachment`, `image`, `video`, `audio`, `pdf`, `writeFile`, `File.write`, `public/`, `static/`, `tmp`, `S3`, `GCS`, `Blob`, `signed`, `CDN`, `cache-control`, and `content-type`.

## Output

Report every upload/storage/delivery path:

| Asset path | Storage | Delivery | Access control | Finding |
|---|---|---|---|---|
| `path/file:line` | local disk/object storage/etc. | app/CDN/signed URL | public/private | issue |

For each finding include risk, expected production failure mode, suggested storage/CDN fix, and tests or deploy checks to verify behavior.
