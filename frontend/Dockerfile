FROM node:14 AS build

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

ARG BASE_URL

RUN sed -i "s|BASE_URL_PLACEHOLDER|${BASE_URL}|g" script.js

FROM nginx:alpine
COPY --from=build /app /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
