.PHONY: install

# Force-reinstall yaam from the current checkout into the uv tool environment.
# For the newest commits from origin, run `git pull` first, then `make install`.
install:
	uv tool install --force .
