#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <algorithm>

#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/model.h"

static std::vector<float> softmax(const std::vector<float>& x) {
    float maxv = *std::max_element(x.begin(), x.end());
    std::vector<float> ex(x.size());
    float sum = 0.0f;
    for (size_t i = 0; i < x.size(); i++) {
        ex[i] = std::exp(x[i] - maxv);
        sum += ex[i];
    }
    for (size_t i = 0; i < x.size(); i++) {
        ex[i] /= sum;
    }
    return ex;
}

int main(int argc, char** argv) {
    // Usage:
    //   ./tflite_infer model.tflite frame.int8
    //   ./tflite_infer --print-quant model.tflite
    if (argc != 3) {
        std::cerr << "Usage:\n"
                  << "  " << argv[0] << " <model.tflite> <frame.int8>\n"
                  << "  " << argv[0] << " --print-quant <model.tflite>\n";
        return 2;
    }

    const std::string arg1 = argv[1];

    // ---------------------------
    // MODE 1: print quant params
    // ---------------------------
    if (arg1 == "--print-quant") {
        const std::string model_path = argv[2];

        auto model = tflite::FlatBufferModel::BuildFromFile(model_path.c_str());
        if (!model) {
            std::cerr << "ERROR: could not load model: " << model_path << "\n";
            return 3;
        }

        tflite::ops::builtin::BuiltinOpResolver resolver;
        std::unique_ptr<tflite::Interpreter> interpreter;
        tflite::InterpreterBuilder(*model, resolver)(&interpreter);
        if (!interpreter) {
            std::cerr << "ERROR: could not build interpreter\n";
            return 4;
        }

        if (interpreter->AllocateTensors() != kTfLiteOk) {
            std::cerr << "ERROR: AllocateTensors failed\n";
            return 5;
        }

        int input_idx = interpreter->inputs()[0];
        int out_idx = interpreter->outputs()[0];

        TfLiteTensor* input = interpreter->tensor(input_idx);
        TfLiteTensor* out = interpreter->tensor(out_idx);

        // Machine-parseable output for Python:
        // INPUT <scale> <zero_point>
        // OUTPUT <scale> <zero_point>
        std::cout << "INPUT " << input->params.scale << " " << input->params.zero_point << "\n";
        std::cout << "OUTPUT " << out->params.scale << " " << out->params.zero_point << "\n";
        return 0;
    }

    // ---------------------------
    // MODE 2: normal inference
    // ---------------------------
    const std::string model_path = argv[1];
    const std::string frame_path = argv[2];

    // Hardcode labels (matches Edge Impulse order)
    const std::vector<std::string> labels = {
        "background",
        "boston_tea_party_tea_earl",
        "polar_seltzer_lime",
        "polar_seltzer_rasp_lime"
    };

    // Load model
    auto model = tflite::FlatBufferModel::BuildFromFile(model_path.c_str());
    if (!model) {
        std::cerr << "ERROR: could not load model: " << model_path << "\n";
        return 3;
    }

    tflite::ops::builtin::BuiltinOpResolver resolver;
    std::unique_ptr<tflite::Interpreter> interpreter;
    tflite::InterpreterBuilder(*model, resolver)(&interpreter);
    if (!interpreter) {
        std::cerr << "ERROR: could not build interpreter\n";
        return 4;
    }

    if (interpreter->AllocateTensors() != kTfLiteOk) {
        std::cerr << "ERROR: AllocateTensors failed\n";
        return 5;
    }

    // Validate input tensor
    int input_idx = interpreter->inputs()[0];
    TfLiteTensor* input = interpreter->tensor(input_idx);
    if (!input || input->type != kTfLiteInt8) {
        std::cerr << "ERROR: expected int8 input tensor\n";
        return 6;
    }

    // Expect [1,96,96,3]
    if (input->dims->size != 4 ||
        input->dims->data[0] != 1 ||
        input->dims->data[1] != 96 ||
        input->dims->data[2] != 96 ||
        input->dims->data[3] != 3) {
        std::cerr << "ERROR: unexpected input shape\n";
        return 7;
    }

    // Read int8 frame bytes (96*96*3)
    const size_t expected_bytes = 96 * 96 * 3;
    std::vector<int8_t> frame(expected_bytes);

    {
        std::ifstream f(frame_path, std::ios::binary);
        if (!f) {
            std::cerr << "ERROR: could not open frame file: " << frame_path << "\n";
            return 8;
        }
        f.read(reinterpret_cast<char*>(frame.data()), expected_bytes);
        if (static_cast<size_t>(f.gcount()) != expected_bytes) {
            std::cerr << "ERROR: frame file wrong size (expected " << expected_bytes
                      << " bytes)\n";
            return 9;
        }
    }

    // Copy into input tensor
    int8_t* in = interpreter->typed_tensor<int8_t>(input_idx);
    std::copy(frame.begin(), frame.end(), in);

    // Run inference
    if (interpreter->Invoke() != kTfLiteOk) {
        std::cerr << "ERROR: Invoke failed\n";
        return 10;
    }

    // Output tensor
    int out_idx = interpreter->outputs()[0];
    TfLiteTensor* out = interpreter->tensor(out_idx);
    if (!out || out->type != kTfLiteInt8) {
        std::cerr << "ERROR: expected int8 output tensor\n";
        return 11;
    }

    // Expect [1,4]
    if (out->dims->size != 2 || out->dims->data[0] != 1) {
        std::cerr << "ERROR: unexpected output shape\n";
        return 12;
    }
    int num_classes = out->dims->data[1];
    if (num_classes <= 0) {
        std::cerr << "ERROR: invalid class count\n";
        return 13;
    }

    // Dequantize output to float logits
    const float out_scale = out->params.scale;
    const int out_zero = out->params.zero_point;

    const int8_t* out_q = interpreter->typed_tensor<int8_t>(out_idx);
    std::vector<float> logits(num_classes);
    for (int i = 0; i < num_classes; i++) {
        logits[i] = (static_cast<int>(out_q[i]) - out_zero) * out_scale;
    }

    // Softmax to probabilities
    std::vector<float> probs = softmax(logits);

    // Find top class
    int top = 0;
    for (int i = 1; i < num_classes; i++) {
        if (probs[i] > probs[top]) top = i;
    }

    std::string label = (top < (int)labels.size()) ? labels[top] : std::to_string(top);
    float conf = probs[top];

    // Output format: "<label> <confidence>"
    std::cout << label << " " << conf << "\n";
    return 0;
}