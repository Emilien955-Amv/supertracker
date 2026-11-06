import { configure } from "@testing-library/react";

// Délai d'attente des « findBy… » : 3 s au lieu d'1 s. Sur une machine
// chargée (CI, Docker sous Windows), 1 s provoquait des échecs aléatoires.
configure({ asyncUtilTimeout: 3000 });
