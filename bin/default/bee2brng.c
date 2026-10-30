#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <bee2/crypto/brng.h>
#include <bee2/core/hex.h>

typedef unsigned char octet;

static void printHex(const octet* buf, size_t count) {
	for (size_t i = 0; i < count; i++) {
		printf("%02X", buf[i]);
	}
}

static octet* fromHex(const char* hex, size_t* len) {
	size_t n = strlen(hex);
	if (n % 2 != 0 || !hexIsValid(hex)) {
		return NULL;
	}
	*len = n / 2;
	octet* buf = malloc(*len ? *len : 1);
	if (*len) {
		hexTo(buf, hex);
	}
	return buf;
}

/*
*******************************************************************************
Обработка команд
*******************************************************************************
*/

static int handleCtr(const char* x_hex, const char* key_hex, const char* s_hex, const char* n_str) {
	size_t x_len, key_len, s_len;
	octet* x = fromHex(x_hex, &x_len);
	octet* key = fromHex(key_hex, &key_len);
	octet* s = fromHex(s_hex, &s_len);
	if (!x || !key || !s || key_len != 32 || s_len != 32 ||
		(n_str && x_len != 32 * (size_t)strtoul(n_str, NULL, 10))) {
		fprintf(stderr, "Invalid arguments\n");
		return 1;
	}

	err_t error = brngCTRRand(x, x_len, key, s);
	if (error != ERR_OK) {
		fprintf(stderr, "Error: %i", error);
		return 1;
	}

	printHex(x, x_len);
	free(x); free(key); free(s);
	return 0;
}

static int handleHmac(const char* key_hex, const char* s_hex, const char* n_str) {
	size_t key_len, s_len;
	octet* key = fromHex(key_hex, &key_len);
	octet* s = fromHex(s_hex, &s_len);
	size_t n = (size_t)strtoul(n_str, NULL, 10);
	if (!key || !s || n == 0) {
		fprintf(stderr, "Invalid arguments\n");
		return 1;
	}

	octet* y = malloc(32 * n);
	err_t error = brngHMACRand(y, 32 * n, key, key_len, s, s_len);
	if (error != ERR_OK) {
		fprintf(stderr, "Error: %i", error);
		return 1;
	}

	printHex(y, 32 * n);
	free(y); free(key); free(s);
	return 0;
}

int main(int argc, char* argv[]) {
	if (argc < 2) {
		fprintf(stderr, "No mode passed\n");
		return 1;
	}

	if (strcmp(argv[1], "brng-ctr") == 0 && (argc == 5 || argc == 6)) {
		return handleCtr(argv[2], argv[3], argv[4], argc == 6 ? argv[5] : NULL);
	}
	if (strcmp(argv[1], "brng-hmac") == 0 && argc == 5) {
		return handleHmac(argv[2], argv[3], argv[4]);
	}

	fprintf(stderr, "Unknown command or wrong argument count: %s\n", argv[1]);
	return 1;
}
