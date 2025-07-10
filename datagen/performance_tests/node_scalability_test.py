import os
import sys
sys.path.append("..")

from datagen.src.start_app import start
from setup import setUp_basic, setUp_complex
from pycompss.api.task import task


@task()
def main(result_dir=None, *args):
    (dimensions, n_samples, rel_tolerance, func, max_depth, use_sensitivity,
     ax, divs_per_cell, plot_boxplot) = setUp_complex()
    cases_df, dims_df, execution_logs = start(dimensions, n_samples,
                                              rel_tolerance, func, max_depth,
                                              use_sensitivity=use_sensitivity,
                                              ax=ax, divs_per_cell=2, seed=4)
    if result_dir != None:
        os.makedirs(result_dir, exist_ok=True)

        for file in os.listdir(result_dir):
            file_path = os.path.join(result_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting files within {file_path}: {e}")

        cases_df.to_csv(os.path.join(result_dir, "cases_df.csv"), index=False)

        dims_df.to_csv(os.path.join(result_dir, "dims_df.csv"), index=False)

        with open(os.path.join(result_dir, "execution_logs.txt"), "w") as log_file:
            for log_entry in execution_logs:
                log_file.write("Dimensions:\n")
                for dim in log_entry[0]:
                    log_file.write(f"{dim}\n")
                log_file.write(f"Entropy: {log_entry[1]}\n")
                log_file.write(f"Delta Entropy: {log_entry[2]}\n")
                log_file.write(f"Depth: {log_entry[3]}\n")
                log_file.write("\n")


if __name__ == "__main__":
    main()
