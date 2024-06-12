import requests
import json

def main(args=None):
    url = "http://localhost:11434/api/generate"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "model": "codellama:7b",
        "prompt": "",
        "stream": False,
        "system": "You are an expert coder who provides simple python code based on the given prompt. You only provide code that executes itself, including any necessary method calls to make the code run. Provide no explanations and no extra characters. Make sure to handle any type conversions from the input. Any extra instructions should be printed to the terminal, not left in the code, so that the code will run without error. Make the code as efficient as possible."
        #"system": "You are an expert coder who provides simple python code using ROS2 to control an iRobot Create3 robot based on the given prompt. You only provide code that executes itself, including any necessary method calls to make the code run. Provide no explanations and no extra characters. Make sure to handle any type conversions from the input. Any extra instructions should be printed to the terminal not left in the code, so that the code will run without error. Make the code as efficient as possible."
    }
    data["prompt"] = input("\nWhat can I create for you?\n")
    while data["prompt"] != "STOP":
        for x in range(2):
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data))
                if response.status_code == 200:
                    response_text = response.text
                    code = json.loads(response.text)["response"]
                    code = code.replace("```", "")
                    print("\n\nBegin Code", code, "End Code\n\n")
                    print("Begin Code Output")
                else:
                    print( "API Error:", response.status_code, response.text)
                exec(code, globals())
            except Exception as e:
                print(e)
                if x==1:
                    print("Process Failed\n\n")
                else:
                    print("Trying Again\n\n")
            else:
                print("End Code Output\n\n")
                break
        data["prompt"] = input("\nWhat can I create for you?\n")
   
if __name__ == '__main__':
    main()