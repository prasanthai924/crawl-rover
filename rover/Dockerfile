# Crawl-space rover — runs on Raspberry Pi 3 Model B (64-bit Raspberry Pi OS Lite, Bookworm)
# Everything comes from apt (prebuilt ARM packages) so the build is fast even on the Pi 3.
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# Add the Raspberry Pi apt repo: picamera2 + libcamera only ship there
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
      | gpg --dearmor -o /usr/share/keyrings/raspberrypi.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/raspberrypi.gpg] http://archive.raspberrypi.com/debian/ bookworm main" \
      > /etc/apt/sources.list.d/raspi.list \
 && apt-get update && apt-get install -y --no-install-recommends \
      python3 \
      python3-picamera2 \
      python3-serial \
      python3-flask \
      python3-requests \
      python3-numpy \
      python3-opencv \
 && apt-get purge -y gnupg && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app/ /app/

# /data holds taught routes (routes/*.json) and captured photos (photos/YYYY-MM-DD/*.jpg)
VOLUME ["/data"]
EXPOSE 8080

# server.py: web joystick (teach mode) + REST endpoints (/replay, /status) for Home Assistant
CMD ["python3", "server.py"]
