#import light python image
FROM python:3.11-slim

#set workdir inside conteainer
WORKDIR /app

# copyu all files to container
COPY . . 

#copy certificate to root postgresql path
RUN mkdir -p /root/.postgresql && cp root.crt /root/.postgresql/root.crt

#install libraries
RUN pip install requests python-dotenv psycopg2-binary

#Run only the requested year-77 colleges: De Anza, Foothill, and West Valley.
CMD ["python", "-m", "scraper.scrape_selected_colleges"]
