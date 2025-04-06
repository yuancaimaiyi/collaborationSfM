# collaborationSfM：众包式结构光恢复系统（Structure-from-Motion）

一个基于 COLMAP 的后端系统，支持多个用户协同上传图像数据，并异步触发同一区域的三维重建任务。

## ✨ 功能亮点

- ✅ 多用户协作上传图像数据
- ✅ 基于 Celery + Redis 的异步任务队列
- ✅ 在不改动 SQLite 的前提下解决并发写入问题
- ✅ 提供 RESTful API（FastAPI 实现）
- 🚧 前端部分开发中

---

## 📦 技术栈

- **COLMAP**：用于三维重建（SfM）
- **FastAPI**：提供后端 API 接口
- **Celery + Redis**：任务异步调度
- **SQLite**：轻量级本地数据库（仅支持读写串行）
- **Python 3.9+**

---

## 📡 API 接口说明

| 方法 | 接口地址 | 描述 |
|------|----------|------|
| `POST` | `/create_region/` | 创建新的重建区域 |
| `POST` | `/upload_images/{region_name}/` | 上传一张或多张图像 |
| `POST` | `/upload_folder/{region_name}/` | 上传图像文件夹 |
| `POST` | `/upload_zip/{region_name}/` | 上传 ZIP 压缩包 |
| `POST` | `/reconstruct/{region_name}/` | 触发该区域的重建任务 |
| `GET`  | `/uploads/{region_name}/` | 查询某区域的上传记录 |

---

## 🧪 使用示例

### 1. 创建一个重建区域

```bash
curl -X POST "http://localhost:8000/create_region/?region_name=garden"
curl -X POST "http://localhost:8000/upload_zip/garden/" \
     -F "zip_file=@/home/yourname/路径/user1.zip" \
     -F "user_id=user1"
# 启动 Redis（监听 6380 端口）
redis-server --port 6380

# 启动 Celery Worker
celery -A collaborationSfM.celery_app worker --loglevel=info
