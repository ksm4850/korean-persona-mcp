import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="korean-persona-mcp",
        description="NVIDIA Nemotron-Personas-Korea 데이터셋을 노출하는 MCP 서버",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="stdio 대신 streamable-http 서버로 실행",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="HTTP 호스트 (기본값 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="HTTP 포트 (기본값 8080)",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="데이터셋 다운로드와 인제스트만 수행하고 종료 (서버 미기동)",
    )
    args = parser.parse_args()

    if args.bootstrap:
        from data import ensure_dataset

        path = ensure_dataset()
        print(f"데이터셋 준비 완료: {path}", file=sys.stderr)
        return

    from server import run_http, run_stdio

    if args.http:
        run_http(args.host, args.port)
    else:
        run_stdio()


if __name__ == "__main__":
    main()
