FROM nvidia/cuda:12.8.0-devel-ubuntu22.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN git clone --depth 1 \
    https://github.com/ggml-org/whisper.cpp.git .

RUN cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=OFF \
        -DGGML_CUDA=ON \
        -DGGML_NATIVE=OFF \
        -DCMAKE_CUDA_ARCHITECTURES=86 \
    && cmake --build build \
        --config Release \
        --target whisper-cli whisper-server \
        -j2


FROM nvidia/cuda:12.8.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder \
    /src/build/bin/whisper-cli \
    /usr/local/bin/whisper-cli

COPY --from=builder \
    /src/build/bin/whisper-server \
    /usr/local/bin/whisper-server

EXPOSE 9002

CMD ["whisper-server", "--host", "0.0.0.0", "--port", "9002", "--model", "/models/ggml-large-v3-turbo-q5_0.bin", "--language", "en"]