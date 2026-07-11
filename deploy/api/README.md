# API Deploy Folder

Folder ini berisi file deploy runtime untuk backend FastAPI Sobat Ngaji.

## Isi

- `Dockerfile`: deploy container untuk Render.
- `requirements.txt`: dependency runtime minimal untuk API + ONNX inference.
- `../../render.yaml`: Render Blueprint untuk Web Service.
- `../../.dockerignore`: membatasi build context agar dataset/checkpoint/cache tidak ikut.

## Rekomendasi

Untuk demo Flutter yang butuh inference model, pakai Render Web Service dengan Docker.
Di Render pilih:

```text
New > Blueprint
```

atau:

```text
New > Web Service > Docker
```

Set Dockerfile path:

```text
deploy/api/Dockerfile
```

Build context:

```text
.
```

Local test:

```bash
docker build -f deploy/api/Dockerfile -t sobat-ngaji-api .
docker run --rm -p 7860:10000 sobat-ngaji-api
```

Base URL lokal:

```text
http://127.0.0.1:7860
```

Swagger:

```text
http://127.0.0.1:7860/docs
```

## Model Files

Endpoint evaluation butuh file berikut tersedia di runtime:

```
external/zipformer_p-quran/quran_phoneme_zipformer.int8.onnx
external/zipformer_p-quran/tokens.txt
external/zipformer_p-quran/quran_text2phoneme.json
external/zipformer_p-quran/data/reference/quran_verses_uthmani.json
```

Kalau model belum masuk repo deploy, backend tetap start, tapi `/evaluate` akan return error model missing.

Untuk production yang lebih rapi, download model dari storage/HF Model repo saat startup atau bake model ke image.
