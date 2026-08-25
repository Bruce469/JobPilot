"""启动入口：python run.py [--host HOST] [--port PORT]

端口被占用时自动探测可用端口（架构 1.3 端口策略）。
"""
import argparse
import socket

from app import config


def find_free_port(host: str, preferred: int) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, preferred))
        return s.getsockname()[1]
    except OSError:
        pass
    finally:
        s.close()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return s.getsockname()[1]
    finally:
        s.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="秋招投递助手后端（仅监听本机）")
    parser.add_argument("--host", default=config.HOST)
    parser.add_argument("--port", type=int, default=config.PORT)
    args = parser.parse_args()

    port = find_free_port(args.host, args.port)
    if port != args.port:
        print(f"[warn] 端口 {args.port} 被占用，改用可用端口 {port}")
    print(f"后端启动：http://{args.host}:{port} （仅本机 127.0.0.1 可访问）")
    print(f"token：{config.TOKEN}（GET /api/boot 获取；重启后重新生成）")

    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=port, log_level="info")


if __name__ == "__main__":
    main()
