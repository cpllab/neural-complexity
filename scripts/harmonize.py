import pandas as pd
import sys


def harmonize_rows(ref, d):
    result = []
    curr_d = d.pop(0)
    curr_ref = ref.pop(0)
    
    while len(d) > 10:
        #print(curr_d[2] + " " + curr_ref[0])
        if curr_d[0] == curr_ref[0]:
            #print("===" + curr_d[2] + "-" + curr_ref[0])
            result.append(curr_d + curr_ref)
            curr_d = d.pop(0)
            curr_ref = ref.pop(0)
        # If current token is unked, then pop both
        elif "unk" in curr_d[0]:
            curr_d = d.pop(0)
            curr_ref = ref.pop(0)
        # If current ref has punctuation, pop both
        elif not curr_ref[0].isalpha():
            curr_ref = ref.pop(0)
            curr_d = d.pop(0)
        #If the current word is the end of a line
        elif "eol" in curr_ref[0]:
            curr_ref = ref.pop(0)
            curr_d = d.pop(0)
        else:
            curr_d = d.pop(0)
            
    return result


def harmonize(rt_path, surps_path, output_path):
  
  try:
    sprt = pd.read_csv(rt_path, index_col=False)
  except:
    print("Invalid path to human reading time csv")

  try:
    surps = pd.read_csv(surps_path, sep="\t", index_col=False)
  except:
    print("Invalid path to model output csv")

  spr_vals = [tuple(x) for x in sprt.values]
  surps_vals = [tuple(x)[2:] for x in surps.values]
  result = harmonize_rows(spr_vals, surps_vals)
  df = pd.DataFrame(result)
  df.columns = ["Word", "surprisal", "Word_2", "code", "s001", "s002","s003","s004", "s005", "s006", "s007", "s008", "s009", "s010",
   "s011", "s012", "s013", "s014", "s015", "s016", "s017", "s018", "s019", "s020", "s021", "s022", "s023", "s024", "s025",
   "s026", "s027", "s028", "s029", "s030", "s031", "s032", "s033", "s034", "s035", "mean_rt"]
  df = df.drop(["Word_2"], axis=1)
  df.to_csv(output_path)

if __name__ == "__main__":
  harmonize(*sys.argv[1:])