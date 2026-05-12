# Introduction

This repository contains all necessary to install and execute in your machine the interface to visualize drone's camera, show a realtime pointcloud and build 3D reconstruction using gaussian splatting algorithm.

# 1 - Requirements

- Computer with NVIDIA's GPU
- Docker
- Nvidia container toolkit

# 2 - Installation

## 2.1 Clone repository

```
git clone https://github.com/barretto-dev/index-scripts.git
```

## 2.2 Create docker image

Before start image's creation, open DockerFile and you will find the follow line at the beginning:

```
ENV TORCH_CUDA_ARCH_LIST="8.9"
```

Search on internet the compatible value of this variable to your GPU and change it on Dockerfile. Searching example: TORCH_CUDA_ARCH_LIST RTX 5060.

After update Dockerfile, create image with:

```
docker build -t gaussian-splatting .
```

## 2.3 Create docker container

Command bellow creates contained called "gs"

```
docker-compose up -d
```

To stop it:

```
docker-compose down
```