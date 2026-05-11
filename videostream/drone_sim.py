import asyncio
import argparse
import os
import websockets

WS_HOST = "127.0.0.1"
WS_PORT = 8765


def parse_args():
    parser = argparse.ArgumentParser(description="Serve um vídeo via WebSocket usando FFmpeg.")
    parser.add_argument(
        "video",
        nargs="?",
        default="videos/video.mp4",
        help="Caminho do vídeo de entrada.",
    )
    parser.add_argument(
        "--resize",
        type=float,
        default=1.0,
        help="Fator para reduzir a resolução. Ex.: --resize 2 deixa largura e altura pela metade.",
    )
    args = parser.parse_args()

    if args.resize <= 0:
        parser.error("--resize deve ser maior que zero")

    return args


ARGS = parse_args()
VIDEO_PATH = os.path.abspath(ARGS.video)


async def handler(ws, path=None):
    print(f"Cliente conectado: {ws.remote_address}, path={path}")

    if not os.path.exists(VIDEO_PATH):
        print(f"ERRO: vídeo não encontrado: {VIDEO_PATH}")
        await ws.close()
        return

    ffmpeg_cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",

        "-re",
        "-stream_loop", "-1",
        "-i", VIDEO_PATH,

        "-an",
    ]

    if ARGS.resize != 1:
        ffmpeg_cmd.extend([
            "-vf", f"scale=iw/{ARGS.resize}:ih/{ARGS.resize}",
        ])

    ffmpeg_cmd.extend([
        "-c:v", "mpeg1video",
        "-pix_fmt", "yuv420p",
        "-b:v", "1500k",
        "-bf", "0",

        "-muxdelay", "0.001",
        "-f", "mpegts",
        "pipe:1",
    ])

    proc = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        while True:
            chunk = await proc.stdout.read(8192)

            if not chunk:
                err = await proc.stderr.read()
                if err:
                    print("FFmpeg stderr:")
                    print(err.decode(errors="ignore")[-1000:])
                break

            await ws.send(chunk)

    except websockets.exceptions.ConnectionClosed as e:
        print(f"Cliente desconectou: code={e.code}, reason={e.reason}")

    except Exception as e:
        print(f"Erro no envio: {e}")

    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

        print("Sessão finalizada")


async def main():
    print(f"Vídeo: {VIDEO_PATH}")
    print(f"Resize: {ARGS.resize}x")
    print(f"Servidor WebSocket em ws://{WS_HOST}:{WS_PORT}")

    async with websockets.serve(
        handler,
        WS_HOST,
        WS_PORT,
        max_size=None,
        compression=None,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor parado.")

