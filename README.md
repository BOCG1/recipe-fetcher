# Recipe Fetcher

A local recipe fetcher that extracts clean, scalable recipes from any URL. Optimized for iPad use in the kitchen.

## Starting it

**Double-click "Recipe Fetcher" on the Desktop.** Safari opens automatically.

(First time only: a Terminal window will show "Installing dependencies..." for about 30 seconds. After that, launches are instant.)

A Terminal window stays open in the background while it's running — that's normal. Close it when you're done cooking.

## iPad setup (one-time)

1. Start Recipe Fetcher on the Mac (double-click the Desktop icon)
2. Look at the Terminal window — it shows a line like `On iPad/WiFi: http://192.168.1.42:8080`
3. On the iPad, open Safari and type that address
4. **Add to Home Screen:** tap the Share button (square with arrow) > "Add to Home Screen" > tap "Add"

Now there's a "Recipes" icon on the iPad home screen. Tap it anytime (as long as the Mac is running Recipe Fetcher).

## Using the app

1. Paste a recipe URL into the search bar (it auto-fetches on paste)
2. View the recipe with hero image, times, and servings
3. Adjust servings with the number input — ingredients scale automatically
4. Tap an ingredient to cross it off as you go
5. Tap a step to mark it done (circle turns green)

Fetched recipes are cached — they'll load instantly next time, even without internet.

## Stopping it

Close the Terminal window. That's it.

## Troubleshooting

- **"Could not connect to the server"** — Double-click "Recipe Fetcher" on the Desktop to start it
- **Recipe not found** — Some sites (Allrecipes, paywalled sites) block automated access. Try a different source for the same recipe
- **iPad can't connect** — Make sure both devices are on the same WiFi. If it still doesn't work, check: System Settings > Network > Firewall > Options, and allow incoming connections on port 8080
- **To find your Mac's IP manually** — System Settings > Wi-Fi > Details > IP Address

## For Brandon (technical notes)

The Desktop launcher runs `~/recipe-fetcher/start.sh`, which manages a Python venv and starts a FastAPI server on port 8080. The server uses recipe-scrapers as primary parser with JSON-LD and CSS heuristic fallbacks.

```bash
cd ~/recipe-fetcher
./start.sh
```
