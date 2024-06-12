import HTNPlanner
import requests
import json

class LLMConnector:
    def __init__(self, LLM, systemMessage):
        self.url = "http://localhost:11434/api/generate"
        self.headers = {
            "Content-Type": "application/json"
        }
        self.data = {
            "model": LLM,
            "prompt": "",
            "stream": False,
            "system": systemMessage
        }

    def prompt(self, promptMessage):
        self.data["prompt"] = promptMessage
        response = requests.post(self.url, headers=self.headers, data=json.dumps(self.data))
        if response.status_code == 200:
            response_text = response.text
            code = json.loads(response.text)["response"]
            code = code.replace("```", "")
            code = code.replace(" print", "print")
            return code
        else:
            print( "API Error:", response.status_code, response.text)
            return None
        


def main(args=None):
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

    methodCaller = LLMConnector("phi3:3.8b","""The following is a list of rooms and descriptions on the third floor of MCAxiom. 

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
Return only the method call with no extra characters, instructions, explanations, or labels. 
""")
    

    prompt = input("\nWhat can I create for you?\n")
    while prompt != "STOP":
        for x in range(2):
            try:
                code = methodCaller.prompt(prompt)
                print(code)
                exec(code)
            except Exception as e:
                print(e)
                if x==1:
                    print("Process Failed\n\n")
                else:
                    print("Trying Again\n\n")
            else:
                print("End Code Output\n\n")
                break
        prompt = input("\nWhat can I create for you?\n")

if __name__ == '__main__':
    main()