Avatar images for the chat UI

The app uses these files (see AVATAR_ROCKY / AVATAR_USER in frontend/src/App.tsx):

  rocky.png   — Rocky’s avatar (square PNG or JPG, roughly 128–256 px; shown in a circle)
  user.png    — Your avatar for outgoing messages

Optional fallbacks in repo: rocky.svg, user.svg (not used unless you change App.tsx).

If the image fails to load, the UI falls back to “R” / “You” initials.
