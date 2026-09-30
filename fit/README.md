# Fit inputs and accepted sound data

Keep the data needed to reproduce tuning and listening decisions here.
Local experiments, plots, and audit reports belong in the ignored `dev/`
folder. Audio renders belong in the ignored `build/` folder.

The accepted resonance prototypes cover C4, G4, C5 and G5 at medium strength,
plus soft and hard C5 strikes. They use one concert grand. They still await
integration into the main opcode; they do not define selectable profiles.

| File | Purpose |
|---|---|
| [c5-modal-reconstruction.json](c5-modal-reconstruction.json) | Original accepted C5 coefficients and sound hashes |
| [modal-extension.json](modal-extension.json) | Coefficients and output gains for all six approved notes and strikes |
| [modal-attack-refinement.json](modal-attack-refinement.json) | Accepted C4 opening, output gain, and sound hash; replaces the earlier C4 sound |
| [concert-grand-timbre.json](concert-grand-timbre.json) | Current runtime's fit targets and regression limits; listening rejected this tone |
| [piano_fit_v1.json](piano_fit_v1.json) | Input for the maintained analyzer fit adapter |

Preserve the earlier reports as evidence. For C4, combine the resonance
coefficients in `modal-extension.json` with `accepted_synthesis` in
`modal-attack-refinement.json`. The other five accepted sounds keep their
original settings. File paths and script hashes in these reports describe
the runs that produced them; local research files may have moved since then.
