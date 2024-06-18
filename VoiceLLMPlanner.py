import speech_recognition as sr
import os 
import HTNPlanner
import requests
import json
import re
import gtts  
from playsound import playsound  

class LLMConnector: 
    def __init__(self, LLM, systemMessage): #takes the name and a system message as input and creates the dictionary needed to access the llm
        self.url = "http://localhost:11434/api/generate" #local ollama port
        self.headers = {
            "Content-Type": "application/json"
        }
        self.data = {
            "model": LLM,
            "prompt": "",
            "stream": False,
            "system": systemMessage
        }

    def prompt(self, promptMessage): #takes prompt as input, updates dictionary, and creates call to llm through ollama
        self.data["prompt"] = promptMessage 
        response = requests.post(self.url, headers=self.headers, data=json.dumps(self.data)) #posts request to ollama API and recieves response
        if response.status_code == 200: #code for success
            response_text = response.text
            code = json.loads(response.text)["response"] #extracts code from json object
            code = code.replace("```", "") #some llms place these characters around code output
            code = code.replace(" print", "print") #some llms place space before method call
            return code
        else:
            print( "API Error:", response.status_code, response.text)
            return None
        
def getSpeechInput(): #returns result of voice input
        r = sr.Recognizer() #creates instance on speech recognition object
        mic = sr.Microphone() #creates object for microphone
        try:
            with mic as source:
                audio = r.listen(source)
            return r.recognize_wit(audio, key="HGEODKAPMSH73UNQHATKFVWJZUZYKFUZ").lower() #gets transcription from wit.ai (meta) API and returns lower case
        except: #error typically occurs from no input
            print("waiting")
            return getSpeechInput() #tries again

def outputSpeech(text):
    tempSound = gtts.gTTS(text)
    tempSound.save("tempFile.mp3")
    playsound("tempFile.mp3")
    os.remove("tempFile.mp3")

def main(args=None):
    #setup HTNPlanner using methods from HTNPlanner.py
    state = HTNPlanner.State('3rd-floor')
    state.visited = {'Robot1': set()}
    state.loc = {'Robot1': 'R312', 'Package1': 'R322', 'Package2': 'R321'}
    state.connected = {'R312': ['Hallway', 'R314'], 
                       'Hallway': ['R312', 'R314', 'R321'], 
                       'R314': ['R312', 'Hallway'], 
                       'R321': ['Hallway', 'R322'], 
                       'R322': ['R321']}
    planner = HTNPlanner.Planner()
    planner.declare_operators(HTNPlanner.go, HTNPlanner.pick_up, HTNPlanner.put_down)
    planner.declare_methods(HTNPlanner.find_route, HTNPlanner.deliver)
    #Sets up instance of object that is used to generate method calls through ollama API with phi3:3.8b as the model and a description of the floor and task as a system message
    methodCaller = LLMConnector("phi3:instruct","""The following is a list of rooms and descriptions on the third floor of MCAxiom. 

‘R314’ is a classroom with several white boards, TVs on the wall, and furniture that can move around the room. It is one of the larger classrooms.

‘R312’ is Dr. Gabriel (Gabe) Ferrer's office. He is a computer science professor who specializes in artificial intelligence and robotics. 

‘R321’ is the resource library and serves as a study room for students. It contains a large bookshelf with academic journals, a genealogy chart of the department, sitting chairs, blackboards, and a table. 

‘R322’ is the workroom and is located inside of the resource library. It is sort of like a large closet and contains a printer. 

‘Hallway’ is the hallway that runs through the floor. 


The following is a list of packages and their descriptions. 

‘Package1’ is a ream of paper.

‘Package2’ is a pencil. 

The method ‘deliver’ is called in the following format. 
print(planner.anyhop(state, [('deliver', '**package**', '**room**')]))

The method returns a plan to deliver a specified package to the specified room.

You are to create a method call to ‘deliver’ using the specified format by replacing '**package**' with the name of the package and '**room**' with the name of the room as identified from the input. 
Return only a single method call with no extra characters, instructions, explanations, or labels. 
""")
    #Sets up instance of object that is used to evaluate user verification through ollama API with phi3:3.8b as the model and a description of the floor and task as a system message
    classifier = LLMConnector("phi3:3.8b", "You are an expert classifier who determines if the prompt is a positive or negative response. If it is a positive response, output a 1. If it is a negative response or you are unsure, output a 0. Do not include any additional text, explanations, or notes.")
    outputSpeech("Ready for command") 
    prompt = getSpeechInput() #gets first prompt from user
    print("Input: " + prompt)
    while prompt != "stop": #STOP as a flag
        for x in range(2): #to allow a second try with the same prompt if an error is recieved
            try:
                response = 0 #0 for negative verification, 1 for positive verification
                for i in range(5): #allows four additional attempts to fine tune prompt before failing process
                    code = methodCaller.prompt(prompt) #recieves code from llm
                    print(code) #used to print code to terminal during testing
                    indices = [i.start() for i in re.finditer("'", code)] #identifies indicees of apostrophe in method call- these are used to determine where the item and location are in the string
                    outputSpeech("To confirm, would you like " + code[(indices[2]+1):indices[3]] + " to be delivered to " + code[(indices[4]+1):indices[5]] + "?") #uses indices to parse string
                    response = getSpeechInput() #Gets speech to text response from user
                    print("Input: " + response)
                    classification = classifier.prompt(response) #recieves a 0 or 1 as a response from llm
                    if '1' in classification: #user has verified prompt
                        exec(code.partition('\n')[0]) #executes method call, removes any extra lines
                        break #breaks loop because no further fine tuning is needed
                    if i == 4: #process has failed
                        outputSpeech("Unable to verify instructions")
                        break #prevents useless prompt
                    outputSpeech("Please clarify your request") 
                    newInfo = getSpeechInput() #gets clarification from user and 
                    print("Input: " + newInfo)
                    prompt = prompt + newInfo #adds additional instructions to orginial prompt
            except Exception as e:
                print(e) #prints error- most likely comes from running bad method call 
                if x==1: #if this is the second attempt at running code, the process fails
                    outputSpeech("Process failed")
                else: # loops back to try again because there has only been one attempt with that prompt
                    outputSpeech("Trying again")
            else:
                break #breaks loop to recieve new input due to prompt fine tuning failing or code succesfully excecuting
        outputSpeech("Ready for command") 
        prompt = getSpeechInput() #gets new prompt from user 
        print("Input: " + prompt)
if __name__ == '__main__':
    main()