FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm install lucide-react date-fns --legacy-peer-deps
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]