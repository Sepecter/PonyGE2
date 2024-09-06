#!/bin/bash

# 每隔固定时间执行的间隔时间（以秒为单位）
interval=1
# 要执行的命令
command="python ponyge.py --parameters string_match.txt"
num=2
count=1
total=1

for ((i=1; i <= num; i++))
do
  $command &
  disown
done


# 无限循环，直到手动停止脚本
while [ $count -le $total ]
do
  # 执行命令
  $command &
  disown
  # 等待指定的时间间隔
  sleep $interval
  count=$((count + 1))
  echo $count

done