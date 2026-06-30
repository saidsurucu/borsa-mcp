# Migration: FastMCP.app → Google Cloud Run

Bu doküman borsa-mcp'nin FastMCP.app Developer planından Google Cloud Run'a
(europe-west1, KVKK uyumlu) taşınmasını anlatır. Çalışan Python kodu değişmedi;
sadece deploy/port/config katmanı uyarlandı.

## Neden Cloud Run + bu parametreler

Gerçek observability verisinden (ezbere değil):

| Metrik | Değer | Karar |
|--------|-------|-------|
| Tool call/ay | ~3.8M (bursty) | concurrency 80 → az instance |
| Süre | p50 437ms · avg 4.4s · p95 25s · p99 96s | I/O-bound → timeout 120, request-based billing |
| Bellek | peak 399MB · avg 378MB | **512Mi** (1Gi over-provisioned'dı) |
| CPU | aktif kullanım düşük | cpu 1 yeterli |

Cloud Run config: `memory=512Mi, cpu=1, concurrency=80, min-instances=0,
max-instances=10, timeout=120, region=europe-west1`, **request-based billing**
(CPU sadece istek sırasında ayrılır — I/O beklemesinde fatura yok).

## Deploy

```bash
# Tek seferlik bootstrap (deploy-cloudrun.sh içinde yorum olarak da var):
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    secretmanager.googleapis.com artifactregistry.googleapis.com

# EVDS API key'i Secret Manager'a koy (gerçek key'i commit'leme):
printf '%s' 'GERCEK_EVDS_KEY' | gcloud secrets create EVDS_API_KEY \
    --data-file=- --replication-policy=automatic

# Cloud Run runtime SA'ya secret okuma izni:
PROJNUM="$(gcloud projects describe "$(gcloud config get-value project)" --format='value(projectNumber)')"
gcloud secrets add-iam-policy-binding EVDS_API_KEY \
    --member="serviceAccount:${PROJNUM}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Deploy (idempotent — her çalıştırmada yeni revision):
./deploy-cloudrun.sh
```

## Yeni URL (canlı)

Deploy edilen servis URL'i:

```
https://borsa-mcp-112000689847.europe-west1.run.app
```

- **MCP endpoint:** `https://borsa-mcp-112000689847.europe-west1.run.app/mcp`
  **(trailing slash YOK)**
- **Health:** `https://borsa-mcp-112000689847.europe-west1.run.app/health`

> ⚠️ **Trailing slash:** `/mcp/` (slash'lı) FastMCP'nin 307 redirect'ini döndürür
> ve hedef `http://` olur (Cloud Run TLS'i edge'de sonlandırdığı için) — bazı
> istemciler bu http-downgrade redirect'i izleyemez. Her zaman **`/mcp`
> (slash'sız)** kullan. README'deki mevcut referanslar zaten slash'sız, uyumlu.

URL'i tekrar almak için:
```bash
gcloud run services describe borsa-mcp --region europe-west1 \
    --format='value(status.url)'
```

## İstemci config'ini değiştirme

README'deki `https://borsamcp.fastmcp.app/mcp` referanslarını (satır 25, 33, 49)
yeni Cloud Run URL'i ile değiştir:

```jsonc
{
  "mcpServers": {
    "borsa": {
      "serverUrl": "https://borsa-mcp-112000689847.europe-west1.run.app/mcp"
    }
  }
}
```

> README'yi DNS custom domain bağladıktan sonra güncellemek daha temiz olur
> (ör. `borsamcp.<senin-domainin>` → Cloud Run domain mapping). O zaman istemci
> URL'i bir daha değişmez.

## Rollback planı (kesintisiz geçiş)

1. **Paralel çalıştır:** Cloud Run'ı deploy et, FastMCP.app'i **kapatma**. İki
   endpoint aynı anda canlı kalır.
2. **Doğrula:** `curl <cloud-run-url>/health` → 200; bir test tool call at
   (ör. `search_symbol GARAN`); birkaç istemcide yeni URL'i dene.
3. **Geçiş:** İstemci config'lerini / README'yi yeni URL'e çevir. Trafiği
   birkaç gün izle (`gcloud run services logs read borsa-mcp`).
4. **Kes:** Sorun yoksa FastMCP.app aboneliğini iptal et.
5. **Geri dönüş (gerekirse):** İstemci URL'ini eski FastMCP.app adresine çevir;
   FastMCP.app henüz kapatılmadığı için anında geri gelir. `fly.toml` da
   alternatif olarak duruyor (`fly deploy`).

## Doğrulama (deploy sonrası)

```bash
curl https://<cloud-run-url>/health           # 200 + {"status":"healthy",...}
gcloud run services describe borsa-mcp --region europe-west1 \
    --format='value(spec.template.spec.containers[0].resources.limits.memory, spec.template.metadata.annotations)'
# memory=512Mi, autoscaling min=0/max=10, concurrency=80 teyidi
```
