#import light python image
FROM python:3.11-slim

#set workdir inside conteainer
WORKDIR /app

# copyu all files to container
COPY . . 

#install libraries
RUN pip install requests python-dotenv psycopg2-binary

#run the script
CMD ["python", "-m", "scraper.scrape_all"]