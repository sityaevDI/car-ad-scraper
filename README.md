# Polovni scraper

## Overview

This project aims to provide an efficient solution for providing bigger picture of the used cars market in Serbia by web
scraping and aggregating stored data.
It leverages modern technologies such as Docker, Docker Compose, and MongoDB to ensure easy deployment and management.

### Features

* Frontend: Built with **vanilla javascript**, it offers a responsive and user-friendly interface.
* Backend: Powered by **FastAPI**, it ensures robust and efficient data processing.
* Database: Uses **MongoDB** for flexible and scalable data storage.

## Getting Started

These instructions will help you set up and run the project locally using Docker and Docker Compose.

### Prerequisites

1. [Docker](https://docs.docker.com/engine/install/) installed on your machine
2. Docker Compose installed (Comes with Docker Desktop)

### Installation

### Clone the repository:

```sh
git clone https://gitlab.com/deni7850/polovni-scraper.git
cd polovni-scraper
```

### Build and start the containers:

```sh
docker-compose up --build
```

This command will build the Docker images for the frontend, backend, and MongoDB services and start them.

#### Accessing the Application

* Frontend: Open your web browser and go to http://localhost:3000
* Backend: API is accessible at http://localhost:8000. Documentation: http://localhost:8000/docs.
* MongoDB: MongoDB instance is available at http://localhost:27017. Accessible via MongoDB Compass.

#### Stopping the Application

To stop the running containers, press CTRL+C in the terminal where the containers are running or run:

```sh
docker-compose down
```

## License

This project is licensed under the [GNU AGPLv3](https://choosealicense.com/licenses/agpl-3.0/) license.

By contributing to this project, you agree to abide by its terms.

### Contributing

Contributions are welcome! Please fork this repository and submit a pull request with your changes.

### Contact

For any inquiries or support, please contact [sityaevdi@gmail.com].

Thank you for using [Polovni scraper]! We hope it serves your needs well.
