#!/bin/bash

# 每隔固定时间执行的间隔时间（以秒为单位）
interval=5
# 要执行的命令
command="python ponyge.py --parameters code_gen_v2.txt"
#数量统计
count=0
#同时执行次数
times=8
#总执行次数
total=7

#获取进程数量
count_running_processes() {
  pgrep -fl "$command" | grep -v "$0" | wc -l
}

# 循环到指定次数
while [ $count -le $total ]
do

  running=$(count_running_processes)

  # 执行命令
  clear
  echo "command start"
    while [ $running -lt $times ]; do
    $command &
#    echo "Started new instance of '$command'. Total running: $((running + 1))"
    running=$((running + 1))
    count=$((count + 1))
  done
  # 等待指定的时间间隔
  echo "command wait"
  echo $count
  sleep $interval

done

echo "=== All tasks started. Waiting for all remaining processes... ==="

# 等待所有后台任务执行完毕
wait

echo "=== All tasks completed. Script exit. ==="