# EAICS di Vercel

Vercel dapat menerbitkan SPA React/Vite pada folder ini. Di dashboard Vercel, import repository lalu atur Root Directory ke `web-workspace`, Build Command `npm run build`, dan Output Directory `dist`. `vercel.json` menangani navigasi SPA.

Vercel meng-host frontend React/Vite dan fungsi proxy Node.js. API FastAPI, PostgreSQL, Redis, dan MinIO tetap harus berjalan pada server cloud terpisah. Setelah backend cloud berjalan, atur dua environment variable di Vercel untuk Production:

- `API_ORIGIN`: origin publik server API, misalnya `https://api.example.com` (tanpa path).
- `API_BASIC_AUTH`: nilai `username:password` untuk akses Caddy Basic Auth. Simpan hanya sebagai environment variable server-side Vercel; jangan gunakan awalan `VITE_`.

Proxy function di `api/proxy.js` meneruskan request `/v1`, `/internal`, `/healthz`, dan `/readyz` dari Vercel ke API, sambil menyimpan kredensial dari browser. Jika backend belum tersedia, endpoint menjawab `API_NOT_CONFIGURED`.

## Protect the demo

In Vercel Project Settings, enable Deployment Protection with **All Deployments** and **Vercel Authentication**. The proxy holds a server-side credential that can reach the backend; do not leave the Vercel deployment public. People who need access must sign in with a Vercel account allowed on the project. Keep the cloud API behind Caddy Basic Auth as a second gate, and use synthetic data only.

The proxy accepts only HTTPS `API_ORIGIN` values and only forwards `/v1`, `/internal`, `/healthz`, and `/readyz`. API responses are marked `no-store`.

Tanpa API publik, halaman UI tetap dapat dibuka tetapi pemanggilan data dan tindakan aplikasi belum berfungsi. Deployment Vercel tidak menggantikan PostgreSQL, Redis, MinIO, maupun API yang digunakan profil cloud TRD.
