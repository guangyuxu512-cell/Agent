FROM python:3.11-slim

# 设置中文/UTF-8 环境（中文文件名必须）
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 先装依赖（利用 Docker 缓存，改代码不用重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 再复制代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

EXPOSE 8001

CMD ["uvicorn", "app.启动器:app", "--host", "0.0.0.0", "--port", "8001"]