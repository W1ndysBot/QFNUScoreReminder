#!/bin/bash

# 设置项目名称和镜像名称
PROJECT_NAME="qfnu-score-reminder-webserver"
IMAGE_NAME="qfnu-score-reminder-webserver"

# 删除已有的容器
docker rm -f $PROJECT_NAME

# 运行Docker容器
echo "Running Docker container..."
docker run -d -p 5001:5001 -v "$(pwd)":/app --name $PROJECT_NAME $IMAGE_NAME

# 检查容器是否成功启动
if [ $? -ne 0 ]; then
    echo "Docker container failed to start!"
    exit 1
fi

echo "Docker container is running. Access the application at http://localhost:5001" 
