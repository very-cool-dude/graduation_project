#!/bin/bash
echo "---------- Удаление контейнеров, томов и образов... ----------"
sudo docker-compose down --volumes --remove-orphans
sudo docker system prune -af

echo "---------- Перезапуск проекта... ----------"
sudo docker-compose up --build