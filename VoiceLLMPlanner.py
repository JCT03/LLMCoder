import speech_recognition as sr
import os 
import HTNPlanner
import requests
import json
import re
import gtts
import sounddevice
from playsound import playsound  

class LLMConnector: #class used to create calls to Ollama API
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
            response = json.loads(response.text)["response"] #extracts response from json object
            print("Response: " + response) # prints llm response for testing purposes
            return response
        else:
            print( "API Error:", response.status_code, response.text)
            return None

def outputSpeech(text): #method for text to voice output, takes message as input
    tempSound = gtts.gTTS(text) #creates voice recording
    tempSound.save("tempFile.mp3") #saves recording as local file
    playsound("tempFile.mp3") #outputs file as sound
    os.remove("tempFile.mp3") #deletes local file
      
def getSpeechInput(output): #outputs message, returns result of voice input, takes message as input
        outputSpeech(output) #calls outputSpeech to give prompt
        r = sr.Recognizer() #creates instance on speech recognition object
        mic = sr.Microphone() #creates object for microphone
        try:
            with mic as source: #sets microphone as source for speech input
                audio = r.listen(source) #gets audio from input source and saves as variable
            input = r.recognize_sphinx(audio).lower() #gets transcription from wit.ai (meta) API and puts in lower case
            print("Input: " + input) #prints recognized speech for testing purposes
            return input
        except: #error typically occurs from no input
            return getSpeechInput("waiting for input") #tries again


class PackageDeliveryState(): #state in which robot delivers package from current location to a designated destination
    def __init__(self, state, planner): #initiated with current state and planner
        self.state = state 
        self.planner = planner
        #Sets up instance of object that is used to generate method calls through ollama API with phi3:3.8b as the model and a description of the floor and task as a system message
        self.methodCaller = LLMConnector("phi3:instruct","""The following is a list of rooms and descriptions on the third floor of MCAxiom. 

‘R314’ is a classroom with several white boards, TVs on the wall, and furniture that can move around the room. It is one of the larger classrooms.

‘R312’ is Dr. Gabriel (Gabe) Ferrer's office. He is a computer science professor who specializes in artificial intelligence and robotics. 

‘R321’ is the resource library and serves as a study room for students. It contains a large bookshelf with academic journals, a genealogy chart of the department, sitting chairs, blackboards, and a table. 

‘R322’ is the workroom and is located inside of the resource library. It is sort of like a large closet and contains a printer. 

‘Hallway’ is the hallway that runs through the floor. 


The following is a list of packages and their descriptions. 

‘Package1’ is a ream of paper.

‘Package2’ is a pencil. 

Based on the following input, you are to identify a package and the room the user would like the package to be delivered to. 
Output your findings in the following format '**package**', '**room**', replacing **package** with the name of the package and **room** with the name of the room, as identified from the input. Make sure to include the single quotation marks. 
Output only a single room and package in the specifed format with no extra characters, instructions, explanations, or labels.
""")
        #Sets up instance of object that is used to evaluate user verification through ollama API with phi3:3.8b as the model and a description of the floor and task as a system message
        self.classifier = LLMConnector("phi3:3.8b", "You are an expert classifier who determines if the prompt is a positive or negative response. If it is a positive response, output a 1. If it is a negative response or you are unsure, output a 0. Do not include any additional text, explanations, or notes.")
    
    def action(self): #action prompts for instructions and generates plan
        prompt = getSpeechInput("Please provide an item and desination.") #gets item and destination from user through speech input
        for x in range(2): #loop to allow a second try with the same prompt if an error is thrown
            try:
                for i in range(5): #allows four additional attempts to fine tune prompt before failing process
                    deliveryDetails = self.methodCaller.prompt(prompt) #recieves details in specifed format from llm
                    deliveryMethod = "print(self.planner.anyhop(self.state,[('deliver'," + deliveryDetails.partition('\n')[0].replace(" ", "") + ")]))" #puts details of delivery into method call, but removes any additional lines in case of extrenous text, also removes spaces to prevent unexpected indent errors
                    indices = [i.start() for i in re.finditer("'", deliveryDetails)] #identifies indicees of apostrophe in method call- these are used to determine where the item and location are in the string
                    response = getSpeechInput("To confirm, would you like " + deliveryDetails[(indices[0]+1):indices[1]] + " to be delivered to " + deliveryDetails[(indices[2]+1):indices[3]] + "?") #Uses indices to parse string for item and destination, and gets speech to text response from user
                    classification = self.classifier.prompt(response) #recieves a 0 or 1 as a response from llm- 1 indicates positive verification
                    if '1' in classification: #user has verified method call
                        exec(deliveryMethod) #executes method call as code
                        break #breaks loop because no further fine tuning is needed
                    if i == 4: #process has failed
                        outputSpeech("Unable to verify instructions")
                        break #prevents useless prompt
                    newInfo = getSpeechInput("Please clarify your request") #gets clarification from user for fine tuning
                    prompt = prompt + newInfo #adds additional instructions to original prompt
            except Exception as e: #catches any errors in process of creating and running method call
                print(e) #prints error- most likely comes from running bad method call 
                if x==1: #if this is the second attempt at running code, the process fails
                    outputSpeech("Process failed")
                else: # loops back to try again because there has only been one attempt with that prompt
                    outputSpeech("Trying again")
            else:
                break #breaks loop due to prompt fine tuning failing and no code running or code succesfully excecuting (no error thrown)
        return RoutingState(self.state, self.planner) #returns next state to main method, which is the routing state

class DescriptionState(): #state in which llm provides description of state of system
    def __init__(self, state, planner): #initialized with state and planner
        self.state = state
        self.planner = planner
        #creates instance of LLM Connector that sets up model to recieve a list of current locations and describe the sytem
        self.describer = LLMConnector("phi3:instruct","""The following is a list of rooms and descriptions on the third floor of MCAxiom. 

                                    ‘R314’ is a classroom with several white boards, TVs on the wall, and furniture that can move around the room. It is one of the larger classrooms.

                                    ‘R312’ is Dr. Gabriel (Gabe) Ferrer's office. He is a computer science professor who specializes in artificial intelligence and robotics. 

                                    ‘R321’ is the resource library and serves as a study room for students. It contains a large bookshelf with academic journals, a genealogy chart of the department, sitting chairs, blackboards, and a table. 

                                    ‘R322’ is the workroom and is located inside of the resource library. It is sort of like a large closet and contains a printer. 

                                    ‘Hallway’ is the hallway that runs through the floor. 


                                    The following is a list of packages and their descriptions. 

                                    ‘Package1’ is a ream of paper.

                                    ‘Package2’ is a pencil. 
                                                                            
                                    "Robot1' is an iRobot Create3 robot that can deliver items. 

                                    The following is a list of where everything is currently located. Breifly describe where everything is located using common names. Do not provide additional explanations or speculation. 
                                    """)
    def action(self): #action outputs a description of the state of the system
        locations = "" #creates empty string to hold locations of all objects
        for item in self.state.loc: #loops through every item in the state's dictionary
            locations += item + " is located in " + self.state.loc[item] + ". " #adds a sentence for each item saying where it is
        outputSpeech(self.describer.prompt(locations)) #creates call to llm with all locations and outputs resulting description
        return RoutingState(self.state,self.planner) #returns next state to main method, which is the routing state

class QuestionState(): #state in which the user can ask a question for clarification
    def __init__(self, state, planner): #initialized with state and planner
        self.state = state
        self.planner = planner
        #creates local instance of connector that describes the premise of the system and sets the llm up to recieve a list of locations and a question to answer
        self.answerer = LLMConnector("phi3:instruct","""You are part of an artificial intelligence system that controls the movement of the robot. The robot can be navigated between any two rooms and deliver packages. 
                                      
                                    The following is a list of rooms and descriptions on the third floor of MCAxiom, where the robot operates.

                                    ‘R314’ is a classroom with several white boards, TVs on the wall, and furniture that can move around the room. It is one of the larger classrooms.

                                    ‘R312’ is Dr. Gabriel (Gabe) Ferrer's office. He is a computer science professor who specializes in artificial intelligence and robotics. 

                                    ‘R321’ is the resource library and serves as a study room for students. It contains a large bookshelf with academic journals, a genealogy chart of the department, sitting chairs, blackboards, and a table. 

                                    ‘R322’ is the workroom and is located inside of the resource library. It is sort of like a large closet and contains a printer. 

                                    ‘Hallway’ is the hallway that runs through the floor. 


                                    The following is a list of packages and their descriptions. 

                                    ‘Package1’ is a ream of paper.

                                    ‘Package2’ is a pencil. 
                                                                            
                                    "Robot1' is an iRobot Create3 robot that can deliver items. 

                                    The following is a list of where everything is currently located. Then, there will be a question input by a user. Using all of the provided information, please provide a breif answer to the question in paragraph form. 
                                    """)
    def action(self): #action gets question from user and outputs response
        locations = "" #creates empty string to hold all current locations in case user asks
        for item in self.state.loc: #loops through all items in state's dictionary
            locations += item + " is located in " + self.state.loc[item] + ". " #adds sentence for each item that says where it is located
        question = getSpeechInput("What is your question?") #asks user for question and saves it
        outputSpeech(self.answerer.prompt(locations + "Question to be answered: " + question)) #prompts and gets response from llm, outputs reponse
        return RoutingState(self.state,self.planner) #returns next state to main method, which is the routing state

class NavigationState(): #state in which the robot moves from current location to new location
    def __init__(self, state, planner): #initialized with state and planner
        self.state = state
        self.planner = planner
        #Sets up instance of object that is used to generate method calls through ollama API with phi3:3.8b as the model and a description of the floor and task as a system message
        self.methodCaller = LLMConnector("phi3:instruct","""The following is a list of rooms and descriptions on the third floor of MCAxiom. 

‘R314’ is a classroom with several white boards, TVs on the wall, and furniture that can move around the room. It is one of the larger classrooms.

‘R312’ is Dr. Gabriel (Gabe) Ferrer's office. He is a computer science professor who specializes in artificial intelligence and robotics. 

‘R321’ is the resource library and serves as a study room for students. It contains a large bookshelf with academic journals, a genealogy chart of the department, sitting chairs, blackboards, and a table. 

‘R322’ is the workroom and is located inside of the resource library. It is sort of like a large closet and contains a printer. 

‘Hallway’ is the hallway that runs through the floor. 

Based on the following input, you are to identify the room the user would like the package to be delivered to. 
Output your findings in the following format '**room**', replacing **room** with the name of the room, as identified from the input. Make sure to include the single quotation marks. 
Output only a single room in the specifed format with no extra characters, instructions, explanations, or labels.
""")
        #Sets up instance of object that is used to evaluate user verification through ollama API with phi3:3.8b as the model 
        self.classifier = LLMConnector("phi3:3.8b", "You are an expert classifier who determines if the prompt is a positive or negative response. If it is a positive response, output a 1. If it is a negative response or you are unsure, output a 0. Do not include any additional text, explanations, or notes.")
    
    def action(self): #action gets location from user and generates plan for robot to travel to location
        prompt = getSpeechInput("Please provide a destination.") #asks user for the destination
        for x in range(2): #to allow a second try with the same prompt if an error is recieved
            try:
                for i in range(5): #allows four additional attempts to fine tune prompt before failing process
                    navigationDetails = self.methodCaller.prompt(prompt) #recieves details in specifed format from llm
                    navigationMethod = "print(self.planner.anyhop(self.state,[('navigate'," + navigationDetails.partition('\n')[0].replace(" ", "") + ")]))" #puts details of delivery into method call, but removes any additional lines in case of extrenous text, also removes spaces to prevent unexpected indent errors
                    indices = [i.start() for i in re.finditer("'", navigationDetails)] #identifies indicees of apostrophe in method call- these are used to determine where the location is in the string
                    response = getSpeechInput("To confirm, would you like the robot to navigate to " + navigationDetails[(indices[0]+1):indices[1]] + "?") #Uses indices to parse string and gets speech to text response from user
                    classification = self.classifier.prompt(response) #recieves a 0 or 1 as a response from llm- 1 indicates postitive verification
                    if '1' in classification: #user has verified method call
                        verified = True
                        exec(navigationMethod)
                        break #breaks loop because no further fine tuning is needed
                    if i == 4: #process has failed
                        outputSpeech("Unable to verify instructions")
                        break #prevents useless prompt
                    newInfo = getSpeechInput("Please clarify your request") #gets clarification from user and 
                    prompt = prompt + newInfo #adds additional instructions to original prompt
            except Exception as e: #catches error from generating and running method call
                print(e) #prints error- most likely comes from running bad method call 
                if x==1: #if this is the second attempt at running code, the process fails
                    outputSpeech("Process failed")
                else: # loops back to try again because there has only been one attempt with that prompt
                    outputSpeech("Trying again")
            else:
                break #breaks loop due to prompt fine tuning failing or code succesfully excecuting
        return RoutingState(self.state,self.planner) #returns next state to main method, which is the routing state

class RoutingState(): #state in which the system determines which state the user would like to access
    def __init__(self, state, planner): #takes state and planner to initialize- not used directly, but necessary for consitency of state machine and to pass to next state
        self.state = state
        self.planner = planner
        #creates instance of llm connector that includes a description of each state and sets the llm up to determine which state the user would like to access
        self.classifier = LLMConnector("phi3:3.8b", """You are part of a larger system that can 
                                       (0) deliver a package
                                       (1) navigate a robot
                                       (2) describe the current state of the system
                                       (3) answer questions regarding the system
                                       Based on the following input, determine which of the abilities the user would like to access and output only the corresponding number, no text. 
                                       """)
    def action(self): #action takes input from user and returns the desired state
        while True: #in loop so that it will try to determine the appropriate state again if the process fails
            request = getSpeechInput("Would you like to deliver a package, navigate the robot, get a description of the system, or ask a question?") #gives user options and recieves reponse
            classification = self.classifier.prompt(request) #prompts llm with user input
            try: 
                num = int(classification) #tries to cast llm response to integer
                if num == 0: #0 means the user wants to deliver a package
                    return PackageDeliveryState(self.state, self.planner) #returns next state which is package delivery
                elif num == 1: #1 means the user wants to navigate the robot
                    return NavigationState(self.state, self.planner) #returns next state which is navigation
                elif num == 2: #2 means the user want a description of the system
                    return DescriptionState(self.state, self.planner) #returns next state which is description
                elif num == 3: #3 means the user wants to ask a question 
                    return QuestionState(self.state, self.planner) #returns next state which is question
                raise Exception("Bad Response") #throws an error 
            except: #catches any errors in case the response is in an improper format
                outputSpeech("Please try again.")

def main(args=None):
    #setup HTNPlanner using methods from HTNPlanner.py
    state = HTNPlanner.State('3rd-floor') #creates new instance of state (imported from HTNPlanner)
    state.visited = {'Robot1': set()} #starts list of visited locations
    state.loc = {'Robot1': 'R312', 'Package1': 'R322', 'Package2': 'R321'} #sets current locations
    state.connected = {'R312': ['Hallway', 'R314'], 
                       'Hallway': ['R312', 'R314', 'R321'], 
                       'R314': ['R312', 'Hallway'], 
                       'R321': ['Hallway', 'R322'], 
                       'R322': ['R321']} #sets adjacency list
    planner = HTNPlanner.Planner() #creates new instance of planner (imported from HTNPlanner.py)
    planner.declare_operators(HTNPlanner.go, HTNPlanner.pick_up, HTNPlanner.put_down) #sets operators available to planner
    planner.declare_methods(HTNPlanner.find_route, HTNPlanner.deliver, HTNPlanner.navigate) #sets methods available to planner
    systemState = RoutingState(state, planner) #sets first state of state machine to routing
    #os.system("ollama run phi3:3.8b /bye") #ensures ollama is open locally
    while True: #continously runs actions of state and gets next state
        systemState = systemState.action() 
    
    
if __name__ == '__main__':
    main()