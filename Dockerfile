# 1. Use the official NVIDIA CUDA 11.8 Development image
FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

# 2. Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# REMEMBER TO CHANGE THIS TO THE VERSION COMPATIBLE WITH GPU!!!!!!!!!!
ENV TORCH_CUDA_ARCH_LIST="8.9"

# 3. Install system dependencies required for Gaussian Splatting and OpenGL
RUN apt-get update && apt-get install -y \
    git \
    wget \
    cmake \
    build-essential \
    libgl1-mesa-dev \
    libglew-dev \
    libglm-dev \
    libxcursor-dev \
    libxinerama-dev \
    libxrandr-dev \
    libxi-dev \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Create the development directory where you will mount your host files
RUN mkdir /development
WORKDIR /development

# 5. Upgrade pip and install PyTorch 2.0.1 compatible with CUDA 11.8
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir torch==2.0.1+cu118 torchvision==0.15.2+cu118 \
    --extra-index-url https://download.pytorch.org/whl/cu118

# 6. Install the basic Python requirements
# Note: These are common to the official repo
RUN pip3 install --no-cache-dir \
    tqdm \
    plyfile \
    opencv-python \
    scipy

# 7. Add a helper script to build the submodules with build isolation disabled
RUN echo 'pip3 install --no-build-isolation /development/gaussian-splatting/submodules/diff-gaussian-rasterization && \
          pip3 install --no-build-isolation /development/gaussian-splatting/submodules/simple-knn' > /usr/local/bin/build_submodules && \
          chmod +x /usr/local/bin/build_submodules
          
#8. Setup the Repository inside the container and build submodules
RUN cd /development && \
    git clone https://github.com/graphdeco-inria/gaussian-splatting --recursive && \
    cd gaussian-splatting && \
    build_submodules

RUN cd /development/gaussian-splatting/submodules/diff-gaussian-rasterization && \
    rm -r build && \
    git checkout 3dgs_accel && \
    python3 -m pip install . --no-build-isolation
    
#9. Install SIBR_viewers needed packages
RUN apt-get update && apt-get install -y \
    libglew-dev \
    libassimp-dev \
    libboost-all-dev \
    libgtk-3-dev \
    libopencv-dev \
    libglfw3-dev \
    libavdevice-dev \
    libavcodec-dev \
    libeigen3-dev \
    libxxf86vm-dev \
    libembree-dev \
    ninja-build \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
    
#10. Build SIBR_viewers
RUN cd /development/gaussian-splatting/SIBR_viewers && \
    cmake -Bbuild . -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 && \
    cmake --build build -j24 --target install
    
#11. Install colmap and ffmpeg
RUN apt-get update && apt-get install -y \
    colmap \
    ffmpeg \
    xvfb \
    mesa-utils

RUN pip install "numpy<2"

#12 Install NODE.js
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

#INSTALL INDEX-INTERFACE
RUN cd /development && \
    git clone https://github.com/barretto-dev/index-interface.git && \
    cd index-interface && \
    npm install

#INSTALL INDEX-BACKEND
RUN cd /development && \
    git clone https://github.com/barretto-dev/index-backend.git && \
    cd index-backend && \
    npm install && \
    npm install -g nodemon

##INSTALL UV + 3D RECON DEEP
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    export PATH="/root/.local/bin:$PATH" && \
    cd /development && \
    git clone https://github.com/argolomb/3d_recon_deep.git && \
    cd 3d_recon_deep && \
    uv venv .venv && \
    uv pip install --python .venv/bin/python \
        opencv-python \
        numpy \
        torch \
        torchvision \
        open3d \
        huggingface_hub \
        pyyaml

#INSTALL DEPTH-ANYTHING 3
RUN cd /development/3d_recon_deep && \
    git clone https://github.com/ByteDance-Seed/depth-anything-3 && \
    cd depth-anything-3 && \
    /root/.local/bin/uv pip install --python ../.venv/bin/python -e .

#INSTALL MODEL Depth Anything 3 Large:
RUN cd /development/3d_recon_deep && \
    .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='depth-anything/DA3-LARGE-1.1', local_dir='models/DA3-LARGE-1.1')"

#INSTALL MODEL Depth Anything 3 Metric Large:
RUN cd /development/3d_recon_deep && \
   .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='depth-anything/DA3METRIC-LARGE', local_dir='models/DA3METRIC-LARGE')"


RUN cd /development && \
    git clone https://github.com/barretto-dev/index-scripts.git && \
    cd index-scripts/videostream && \
    chmod +x mediamtx && \
    pip install websockets

# Set the default shell to bash
CMD ["bash"]
