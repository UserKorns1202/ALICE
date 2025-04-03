# ALICE
Artificial Learning Isolated Companion Entity (ALICE) is a personal project to create a fully offline voice assistant similar to Alexa/Siri/etc as a learning experience for AI and device interaction.

## Version 1: VRGL
The original version of this program started as a basic AI voice assistant that could interact with the system given specific phrases. The main features of this model include:
- GUI of the Superintendent or VRGL from the game Halo 3: ODST as a simple stand in for showing when different actions occured (images from Halopedia page)
- Voice and Text interaction with assistant toggled by talking with it
- Toggled contstant overlay of screen to work with other apps and still have GUI visible
- Ability to switch voices and GUI folder on the fly by switching "mode"
- Opening/Closing of device apps
- Volume control of device
- Uncaught queries pushed to ChatGPT api to get response
- Basic conversational answers covered in program
- Pattern smudging for variations in sentance structure to catch queries
- Read emails to user
- Task list creation and editing (with reminders on boot-up)
- Facial recognition on login for last user
- Screenshot analysis and text extraction

## Version 2: ALICE
Given the redementery architecture of the VRGL model, I wanted to clean up the way I wrote some of that code, make the overall process offline instead of using ChatGPT api for uncaught responses, and make query detection more robust and natural. If VRGL was a focus on functionality, ALICE will start as a focus on form/design. This model has a local LLM and TTS model woven into the files, hoever due to the size of these files not all parts can be stored on GitHub easily.

## Version 3: KEVIN
This version exists in it's own repository as an experiment in taking the ALICE model and running it on a personal NAS device I have setup on a Raspberry Pi. This program will have the capability to edit files and related tasks on the server, as well as be accessible by any user's device connected to the server.
