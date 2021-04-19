# Using Docker

Docker can be used for setting up Postgres for local development. Here is the recommended way to install Docker for Mac and launch the image for Postgres.

1. Install Docker for Mac

```
brew install --cask docker
```

2. Install shell completions

```
brew install docker-completion docker-compose-completion
```

3. Run Docker container

```
docker-compose up
```

or

```
docker-compose up --detach
```

4. Update config to use Postgres instance

Add `DATABASE_URL=postgres://postgres:postgres@localhost:5432/vaccinate` to your .env file in the root of this directory