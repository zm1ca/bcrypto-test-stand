#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <bee2/crypto/bash.h>
#include <bee2/core/hex.h>

typedef unsigned char octet;

static void printHex(const octet* buf, size_t count) {
	for (size_t i = 0; i < count; i++) {
		printf("%02X", buf[i]);
	}
}

/*
*******************************************************************************
Обработка команд
*******************************************************************************
*/

static int handleHash(const char* msg_hex, const char* level_str) {
	size_t level = (size_t)strtoul(level_str, NULL, 10);
	if (level != 128 && level != 192 && level != 256) {
		fprintf(stderr, "Unsupported level: %s\n", level_str);
		return 1;
	}

	size_t len = strlen(msg_hex);
	if (len % 2 != 0 || !hexIsValid(msg_hex)) {
		fprintf(stderr, "Invalid hex message\n");
		return 1;
	}
	len /= 2;

	octet* msg = malloc(len ? len : 1);
	if (len) {
		hexTo(msg, msg_hex);
	}

	octet hash[64];
	err_t error = bashHash(hash, level, msg, len);
	free(msg);
	if (error != ERR_OK) {
		fprintf(stderr, "Error: %i", error);
		return 1;
	}

	printHex(hash, level / 4);
	return 0;
}

int main(int argc, char* argv[]) {
	if (argc < 2) {
		fprintf(stderr, "No mode passed\n");
		return 1;
	}

	if (strcmp(argv[1], "bash") == 0) {
		if (argc != 4) {
			fprintf(stderr, "Expected 2 arguments after mode\n");
			return 1;
		}
		return handleHash(argv[2], argv[3]);
	}

	fprintf(stderr, "Unknown command: %s\n", argv[1]);
	return 1;
}
