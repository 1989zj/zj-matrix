#!/bin/bash
# NovelStudio Web 服务管理

case "$1" in
  start)
    cd ~/NovelStudio/web
    nohup python3 app.py > ~/NovelStudio/web/server.log 2>&1 &
    echo "NovelStudio Web started on port 5003 (PID $!)"
    ;;
  stop)
    pkill -f "python3.*app.py" 2>/dev/null && echo "Stopped" || echo "Not running"
    ;;
  restart)
    $0 stop; sleep 1; $0 start
    ;;
  status)
    pgrep -f "python3.*app.py" > /dev/null && echo "Running on $(hostname -I | awk '{print $1}'):5003" || echo "Not running"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    ;;
esac
