# Panduan Deployment FarmaSigap ke Railway

Proyek ini telah dikonfigurasi lengkap agar dapat langsung di-deploy ke **Railway** (baik backend FastAPI maupun frontend-nya sekaligus dalam 1 layanan).

---

## Opsi 1: Deploy Otomatis via GitHub (Paling Direkomendasikan)

### Langkah 1: Buat Repository di GitHub
1. Buka [github.com/new](https://github.com/new) dan buat repository baru bernama `FarmaSigap` (Public atau Private).
2. Di terminal komputer Anda, hubungkan repository lokal ke GitHub:
   ```bash
   cd /Users/rifqi/Documents/FarmaSigap
   git branch -M main
   git remote add origin https://github.com/<USERNAME-ANDA>/FarmaSigap.git
   git push -u origin main
   ```

### Langkah 2: Hubungkan ke Railway
1. Masuk ke akun [railway.com](https://railway.com/) atau [railway.app](https://railway.app/).
2. Klik tombol **"+ New Project"**.
3. Pilih **"Deploy from GitHub repo"**.
4. Pilih repository **`FarmaSigap`**.
5. Klik **"Deploy Now"**.

Railway akan otomatis membaca file `Procfile` / `railway.json` / `Dockerfile` yang telah kita siapkan.

### Langkah 3: Generate Domain Publik
1. Setelah deployment berstatus *Success*, klik service `FarmaSigap` di dasbor Railway.
2. Buka tab **Settings**.
3. Di bagian **Networking** > **Public Networking**, klik **"Generate Domain"**.
4. Anda akan mendapatkan URL publik resmi, misalnya:
   `https://farmasigap-production.up.railway.app`

---

## Opsi 2: Deploy Cepat via Railway CLI

Jika Anda ingin langsung men-deploy dari terminal tanpa melalui GitHub:

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   # atau jika memakai Homebrew: brew install railway
   ```
2. Login ke akun Railway:
   ```bash
   railway login
   ```
3. Inisialisasi dan upload:
   ```bash
   cd /Users/rifqi/Documents/FarmaSigap
   railway init
   railway up
   ```
4. Tambahkan domain publik:
   ```bash
   railway domain
   ```

---

## URL yang Tersedia Setelah Deploy

Setelah domain aktif:
- **Website Frontend Lengkap**: `https://<domain-anda>.up.railway.app/` atau `https://<domain-anda>.up.railway.app/app/`
- **Dokumentasi API Swagger**: `https://<domain-anda>.up.railway.app/docs`
- **Health Check API**: `https://<domain-anda>.up.railway.app/health`
- **Endpoint API**: `https://<domain-anda>.up.railway.app/api/...`
