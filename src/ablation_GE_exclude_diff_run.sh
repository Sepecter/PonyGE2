#!/bin/bash

# 间隔时间（秒）
interval=5

# 要执行的命令
command="python ponyge.py --parameters abla_GE_exclude_diff.txt"

# 最大并发数
times=2

# 运行总时长（24小时 = 86400秒）
max_duration=$((24 * 60 * 60))

# 记录开始时间（秒级时间戳）
start_time=$(date +%s)

# 启动计数
count=0

# 获取进程数量
count_running_processes() {
  pgrep -fl "$command" | grep -v "$0" | wc -l
}

while true
do
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))

  # 判断是否超过24小时
  if [ $elapsed -ge $max_duration ]; then
    echo "=== Time limit reached (24h). Stop launching new tasks ==="
    break
  fi

  running=$(count_running_processes)

  clear
  echo "=== Running time: ${elapsed}s / ${max_duration}s ==="
  echo "=== Current running: $running / $times ==="

  # 补满并发
  while [ $running -lt $times ]; do
    $command &
    running=$((running + 1))
    count=$((count + 1))
  done

  echo "Total started: $count"
  sleep $interval
done

echo "=== Waiting for all running tasks to finish... ==="

# 等待所有后台任务完成
wait

echo "=== All tasks completed. Script exit. ==="

