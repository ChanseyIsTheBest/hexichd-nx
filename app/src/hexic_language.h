// hexichd-nx (2026-11-04, from pacman-nx, nights-nx and sa2-nx): the toml's "language" (auto, english, japanese, french, german, spanish, italian) as
// the Xbox language the game reads (user_language).
#pragma once

namespace hexic::language {

// Once the config is loaded, before the game starts.
void Apply();

}  // namespace hexic::language
