# Introduction

This repository contains all necessary to install and execute in your machine the interface to visualize drone's camera, show a realtime pointcloud and build 3D reconstruction using gaussian splatting algorithm.

# 1 - Requirements

- Ubuntu
- NVIDIA's GPU
- Docker
- Nvidia container toolkit
- Firefox broswer

# 2 - Installation

## 2.1 Clone repository

```
git clone https://github.com/barretto-dev/index-scripts.git
```

## 2.2 Prepare development volumes (opcional)

In case you want to develop on this aplication, is recommended to create volumes. First is necessary to clones the followers repositories:

```
git clone https://github.com/barretto-dev/index-interface.git
```
```
git clone https://github.com/barretto-dev/index-backend.git
```

After this, modify "docker-compose.yml" to add new volumes
```
volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix:rw
      - ./entrypoint.sh:/entrypoint.sh
      - /PATH/TO/FOLDER/output:/development/gaussian-splatting/output #Volume to 3D reconstruction
      - /PATH/TO/REPOSITORY/index-backend:/development/index-backend
      - /PATH/TO/REPOSITORY/index-interface:/development/index-interface
      - /PATH/TO/REPOSITORY/index-scripts:/development/index-scripts
```


## 2.3 Create docker image

Before start image's creation, open DockerFile and you will find the follow line at the beginning:

```
ENV TORCH_CUDA_ARCH_LIST="8.9"
```

Search on internet the compatible value of this variable to your GPU and change it on Dockerfile. Searching example: TORCH_CUDA_ARCH_LIST RTX 5060.

After update Dockerfile, create image with:

```
docker build -t gaussian-splatting .
```

## 2.4 Create docker container

Before start container, executes:

- Allows the 3D reconstrucion's visualizer (SIBR_viewer) to be open (MUST BE USED EVERYTIME COMPUTER STARTS)

```
--xhost +local:root
```

- Give permission to execute script (only once)
```
chmod +x entrypoint.sh
```

Start container "gs"

```
docker-compose up -d
```

To remove it:

```
docker-compose down
```

# 3 - Access Interface

Open on Firefox: http://127.0.0.1:3000/

# 4 - Test without camera

## 4.1 Show image

To test everything is working fine, First you need execute a script that will get a video and transmit it througt a websocket:

```
cd videostream/test/
python3 drone_sim.py example.mp4
```

Now make sure at Settings CameraWsUrl = 127.0.0.1 and CameraWsUrl = 8765 and save it. After this, click on toogle "Camera OFF" and will be show the video of example.

Case the video is slow or "blinking", stop the script and use it again with --resize parameter to reduce video's resolution

```
python3 drone_sim.py example.mp4 --resize 2
```

## 4.2 - Show PointCloud

Just click on Button "Start PointCloud" and wait to appear, case do not work, change button to "Stop PointCloud", click it and try to start again

## 4.3 - Start 3D Reconstruction

This first step to reconstruction is Record what is show at camera window, to do this click on button "Start Record" and let for al least 20 seconds before stop it. The record generates frames that will be used on reconstruction, it's stored at container directory development/frames/input

