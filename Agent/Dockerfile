# ---- 第一阶段：构建 ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install --ignore-scripts
COPY . .
RUN npm run build

# ---- 第二阶段：用 Nginx 托管静态文件 ----
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 1254
CMD ["nginx", "-g", "daemon off;"]