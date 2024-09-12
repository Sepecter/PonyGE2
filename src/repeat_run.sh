#!/bin/bash

# 每隔固定时间执行的间隔时间（以秒为单位）
interval=5
# 要执行的命令
command="python ponyge.py --parameters code_gen.txt"
num=5
count=1
total=100

for ((i=1; i <= num; i++))
do
  $command &
  disown
done


# 无限循环，直到手动停止脚本
while [ $count -le $total ]
do
  # 执行命令
  clear
  echo "command start"
  $command &
  disown
  # 等待指定的时间间隔
  echo "command wait"
  sleep $interval
  echo "wait"
  count=$((count + 1))
  echo $count

done