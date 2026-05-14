# Deploy Python Backend lên VPS Coolify

## Yêu cầu

- VPS với **Coolify** đã cài đặt
- Domain/subdomain trỏ về VPS (ví dụ: `api.dulichlamdong.vt360.vn`)
- SSL được cấp qua Coolify (Let's Encrypt tự động)

---

## 1. Tạo Service trên Coolify

1. Mở Coolify dashboard → **New Resource** → **Dockerfile**
2. Trỏ tới repo hoặc folder `backend/`
3. Coolify sẽ tự phát hiện `Dockerfile`

---

## 2. Cấu hình Environment Variables

Vào **Environment Variables** trong Coolify và thêm các biến sau:

| Biến | Giá trị | Bắt buộc |
|------|---------|----------|
| `GEMINI_API_KEY` | API key từ Google AI Studio | ✓ |
| `GEMINI_MODEL` | `gemini-2.0-flash-live-001` | ✓ |
| `GEMINI_VOICE` | `Aoede` | ✓ |
| `ADMIN_PASSWORD` | Mật khẩu admin tự đặt | ✓ |
| `SCENE_MAP_JSON` | JSON map scene_id → nodeId | ✓ |

### Giá trị mẫu cho SCENE_MAP_JSON

```json
{"ho-tuyen-lam":"node414","da-lat":"node470","langbiang":"node412","pongour":"node418","tinh-yeu":"node482"}
```

---

## 3. Cấu hình Domain & Port

- **Port**: `8000`
- **Domain**: `api.dulichlamdong.vt360.vn` (hoặc subdomain bạn chọn)
- **HTTPS**: bật (Coolify cấp SSL tự động)

---

## 4. Cấu hình CORS (bắt buộc khi deploy production)

Sau khi có domain DA thật, mở `backend/main.py` và sửa:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # ← domain DA thật
    ...
)
```

Sau đó redeploy.

---

## 5. Kiểm tra sau khi deploy

### Health check

```
GET https://api.dulichlamdong.vt360.vn/health
→ {"status": "ok"}
```

### Admin UI

```
GET https://api.dulichlamdong.vt360.vn/admin
→ Trang admin (yêu cầu Basic Auth với ADMIN_PASSWORD)
```

### WebSocket

```
wss://api.dulichlamdong.vt360.vn/ws
→ Kết nối từ pano2vr_new frontend
```

---

## 6. Cập nhật frontend

Sau khi có domain backend thật, mở `pano2vr_new/js/ai-config.js` và sửa:

```js
wsUrl: 'wss://api.dulichlamdong.vt360.vn/ws',
```

Sau đó upload lại `js/ai-config.js` lên DA.

---

## 7. Endpoints tổng hợp

| Method | Path | Mô tả |
|--------|------|-------|
| `GET` | `/health` | Health check |
| `GET` | `/admin` | Admin UI (Basic Auth) |
| `GET` | `/admin/prompt` | Xem system prompt hiện tại |
| `POST` | `/admin/prompt` | Cập nhật system prompt |
| `GET` | `/admin/config` | Xem model/voice/scene IDs |
| `POST` | `/admin/config` | Hot-reload model và voice |
| `POST` | `/admin/reset` | Reset prompt về mặc định |
| `WS` | `/ws` | Gemini Live proxy (audio I/O) |

---

## 8. Hot-reload model và voice

Không cần restart server. Gọi API:

```bash
curl -X POST https://api.dulichlamdong.vt360.vn/admin/config \
  -u admin:YOUR_ADMIN_PASSWORD \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini-2.0-flash-live-001", "voice": "Kore"}'
```

Thay đổi có hiệu lực với **phiên WebSocket tiếp theo**.

---

## Voices có sẵn

`Aoede` · `Charon` · `Fenrir` · `Kore` · `Puck`
