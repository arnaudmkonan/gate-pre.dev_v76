FROM nginx:alpine

# Copy landing page files
COPY index.html /usr/share/nginx/html/index.html
COPY register.html /usr/share/nginx/html/register.html
COPY demo.webp /usr/share/nginx/html/demo.webp
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
